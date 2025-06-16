# inspired by: https://github.com/xlang-ai/OSWorld/blob/main/desktop_env/server/main.py

import concurrent.futures
import ctypes
import os
import platform
import re
import shlex
import signal
import subprocess
from pathlib import Path
from typing import Any, Sequence, Optional, Union, List
from contextlib import asynccontextmanager
import logging

import lxml.etree
import pyautogui
import requests
import Xlib
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from lxml.etree import _Element
from PIL import Image, ImageGrab
from Xlib import X, display

from .request_models import (
    CommandRequest,
    WindowSizeRequest,
    DirectoryRequest,
    FileRequest,
    UploadRequest,
    WallpaperRequest,
    DownloadRequest,
    OpenFileRequest,
    WindowRequest,
)
from .response_models import (
    CommandResponse,
    DirectoryTreeResponse,
    ScreenSizeResponse,
    WindowSizeResponse,
    DesktopPathResponse,
    PlatformResponse,
    CursorPositionResponse,
    TerminalOutputResponse,
    AccessibilityTreeResponse,
    ErrorResponse,
    RecordingResponse,
    StatusEnum,
)

pyautogui.PAUSE = 0
pyautogui.DARWIN_CATCH_UP_TIME = 0
platform_name: str = platform.system()

if platform_name == "Linux":
    import pyatspi
    from pyatspi import (
        STATE_SHOWING,
        Accessible,
        Component,  # , Document
        StateType,
    )
    from pyatspi import Action as ATAction
    from pyatspi import Text as ATText
    from pyatspi import Value as ATValue

    BaseWrapper = Any

elif platform_name == "Windows":
    import pywinauto.application
    import win32gui
    import win32ui
    from pywinauto import Desktop
    from pywinauto.base_wrapper import BaseWrapper

    Accessible = Any

elif platform_name == "Darwin":
    import AppKit
    import ApplicationServices
    import Quartz

    Accessible = Any
    BaseWrapper = Any

else:
    # Platform not supported
    Accessible = None
    BaseWrapper = Any

from pyxcursor import Xcursor

class DesktopServer:
    def __init__(self):
        self.app = FastAPI(lifespan=self.lifespan)
        self.logger = logging.getLogger("uvicorn.access")
        self.recording_process = None
        self.recording_path = "/tmp/recording.mp4"
        if platform_name == "Linux":
            self.libreoffice_version_tuple = self._get_libreoffice_version()
            self.MAX_DEPTH = 50
            self.MAX_WIDTH = 1024
            self.MAX_CALLS = 5000
        
        # Configure pyautogui
        pyautogui.PAUSE = 0
        pyautogui.DARWIN_CATCH_UP_TIME = 0
        
        # Register all routes
        self._register_routes()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(handler)
        
        yield
        
        if self.recording_process:
            self.recording_process.send_signal(signal.SIGINT)
            self.recording_process.wait()

    def _register_routes(self):
        # Setup routes
        self.app.post("/setup/execute")(self.execute_command)
        self.app.post("/execute")(self.execute_command)
        self.app.post("/setup/launch")(self.launch_app)
        self.app.get("/screenshot")(self.capture_screen_with_cursor)
        self.app.get("/terminal")(self.get_terminal_output)
        self.app.get("/accessibility")(self.get_accessibility_tree)
        self.app.post("/screen_size")(self.get_screen_size)
        self.app.post("/window_size")(self.get_window_size)
        self.app.post("/desktop_path")(self.get_desktop_path)
        self.app.post("/wallpaper")(self.get_wallpaper)
        self.app.post("/list_directory")(self.get_directory_tree)
        self.app.post("/file")(self.get_file)
        self.app.post("/setup/upload")(self.upload_file)
        self.app.get("/platform")(self.get_platform)
        self.app.get("/cursor_position")(self.get_cursor_position)
        self.app.post("/setup/change_wallpaper")(self.change_wallpaper)
        self.app.post("/setup/download_file")(self.download_file)
        self.app.post("/setup/open_file")(self.open_file)
        self.app.post("/setup/activate_window")(self.activate_window)
        self.app.post("/setup/close_window")(self.close_window)
        self.app.post("/start_recording")(self.start_recording)
        self.app.post("/end_recording")(self.end_recording)

    def _get_libreoffice_version(self) -> tuple[int, ...]:
        result = subprocess.run("libreoffice --version", shell=True, text=True, stdout=subprocess.PIPE)
        version_str = result.stdout.split()[1]
        return tuple(map(int, version_str.split(".")))

    async def execute_command(self, request: CommandRequest) -> CommandResponse:
        command = request.command
        shell = request.shell

        for i, arg in enumerate(command):
            if arg.startswith("~/"):
                command[i] = os.path.expanduser(arg)

        try:
            if platform_name == "Windows":
                flags = subprocess.CREATE_NO_WINDOW
            else:
                flags = 0
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
                text=True,
                timeout=120,
                creationflags=flags,
            )
            return CommandResponse(
                status=StatusEnum.SUCCESS,
                message="Command executed successfully",
                output=result.stdout,
                error=result.stderr,
                returncode=result.returncode
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def launch_app(self, request: CommandRequest):
        command = request.command
        shell = request.shell

        for i, arg in enumerate(command):
            if arg.startswith("~/"):
                command[i] = os.path.expanduser(arg)

        try:
            if "google-chrome" in command and self._get_machine_architecture() == "arm":
                index = command.index("google-chrome")
                command[index] = "chromium" # arm64 chrome is not available yet, can only use chromium
            subprocess.Popen(command, shell=shell)
            return f"{command if shell else ' '.join(command)} launched successfully"
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def _get_machine_architecture(self) -> str:
        architecture = platform.machine().lower()
        if architecture in ["amd32", "amd64", "x86", "x86_64", "x86-64", "x64", "i386", "i686"]:
            return "amd"
        elif architecture in ["arm64", "aarch64", "aarch32"]:
            return "arm"
        else:
            return "unknown"

    async def capture_screen_with_cursor(self):
        file_path = os.path.join(os.path.dirname(__file__), "screenshots", "screenshot.png")
        user_platform = platform.system()

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # fixme: This is a temporary fix for the cursor not being captured on Windows and Linux
        if user_platform == "Windows":
            def get_cursor():
                hcursor = win32gui.GetCursorInfo()[1]
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, 36, 36)
                hdc = hdc.CreateCompatibleDC()
                hdc.SelectObject(hbmp)
                hdc.DrawIcon((0, 0), hcursor)

                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                cursor = Image.frombuffer(
                    "RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1
                ).convert("RGBA")

                win32gui.DestroyIcon(hcursor)
                win32gui.DeleteObject(hbmp.GetHandle())
                hdc.DeleteDC()

                pixdata = cursor.load()

                width, height = cursor.size
                for y in range(height):
                    for x in range(width):
                        if pixdata[x, y] == (0, 0, 0, 255):
                            pixdata[x, y] = (0, 0, 0, 0)

                hotspot = win32gui.GetIconInfo(hcursor)[1:3]

                return (cursor, hotspot)

            ratio = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100

            img = ImageGrab.grab(bbox=None, include_layered_windows=True)

            try:
                cursor, (hotspotx, hotspoty) = get_cursor()

                pos_win = win32gui.GetCursorPos()
                pos = (round(pos_win[0] * ratio - hotspotx), round(pos_win[1] * ratio - hotspoty))

                img.paste(cursor, pos, cursor)
            except:
                pass

            img.save(file_path)
        elif user_platform == "Linux":
            cursor_obj = Xcursor()
            imgarray = cursor_obj.getCursorImageArrayFast()
            cursor_img = Image.fromarray(imgarray)
            screenshot = pyautogui.screenshot()
            cursor_x, cursor_y = pyautogui.position()
            screenshot.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
            screenshot.save(file_path)
        elif user_platform == "Darwin":
            # Use the screencapture utility to capture the screen with the cursor
            subprocess.run(["screencapture", "-C", file_path])
        else:
            self.logger.warning(f"The platform you're using ({user_platform}) is not currently supported")

        return FileResponse(file_path, media_type="image/png")

    def _has_active_terminal(self, desktop: Accessible) -> bool:
        """A quick check whether the terminal window is open and active."""
        for app in desktop:
            if app.getRoleName() == "application" and app.name == "gnome-terminal-server":
                for frame in app:
                    if frame.getRoleName() == "frame" and frame.getState().contains(pyatspi.STATE_ACTIVE):
                        return True
        return False

    async def get_terminal_output(self):
        user_platform = platform.system()
        output: str | None = None
        try:
            if user_platform == "Linux":
                desktop: Accessible = pyatspi.Registry.getDesktop(0)
                if self._has_active_terminal(desktop):
                    desktop_xml: _Element = self._create_atspi_node(desktop)
                    # 1. the terminal window (frame of application is st:active) is open and active
                    # 2. the terminal tab (terminal status is st:focused) is focused
                    xpath = '//application[@name="gnome-terminal-server"]/frame[@st:active="true"]//terminal[@st:focused="true"]'
                    terminals: list[_Element] = desktop_xml.xpath(xpath, namespaces=_accessibility_ns_map_ubuntu)
                    output = terminals[0].text.rstrip() if len(terminals) == 1 else None
            else:  # windows and macos platform is not implemented currently
                raise HTTPException(status_code=501, detail=f"Currently not implemented for platform {platform.platform()}.")
            return TerminalOutputResponse(output=output, status="success")
        except Exception as e:
            self.logger.error("Failed to get terminal output. Error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    _accessibility_ns_map = {
        "ubuntu": {
            "st": "https://accessibility.ubuntu.example.org/ns/state",
            "attr": "https://accessibility.ubuntu.example.org/ns/attributes",
            "cp": "https://accessibility.ubuntu.example.org/ns/component",
            "doc": "https://accessibility.ubuntu.example.org/ns/document",
            "docattr": "https://accessibility.ubuntu.example.org/ns/document/attributes",
            "txt": "https://accessibility.ubuntu.example.org/ns/text",
            "val": "https://accessibility.ubuntu.example.org/ns/value",
            "act": "https://accessibility.ubuntu.example.org/ns/action",
        },
        "windows": {
            "st": "https://accessibility.windows.example.org/ns/state",
            "attr": "https://accessibility.windows.example.org/ns/attributes",
            "cp": "https://accessibility.windows.example.org/ns/component",
            "doc": "https://accessibility.windows.example.org/ns/document",
            "docattr": "https://accessibility.windows.example.org/ns/document/attributes",
            "txt": "https://accessibility.windows.example.org/ns/text",
            "val": "https://accessibility.windows.example.org/ns/value",
            "act": "https://accessibility.windows.example.org/ns/action",
            "class": "https://accessibility.windows.example.org/ns/class",
        },
        "macos": {
            "st": "https://accessibility.macos.example.org/ns/state",
            "attr": "https://accessibility.macos.example.org/ns/attributes",
            "cp": "https://accessibility.macos.example.org/ns/component",
            "doc": "https://accessibility.macos.example.org/ns/document",
            "txt": "https://accessibility.macos.example.org/ns/text",
            "val": "https://accessibility.macos.example.org/ns/value",
            "act": "https://accessibility.macos.example.org/ns/action",
            "role": "https://accessibility.macos.example.org/ns/role",
        },
    }

    _accessibility_ns_map_ubuntu = _accessibility_ns_map["ubuntu"]
    _accessibility_ns_map_windows = _accessibility_ns_map["windows"]
    _accessibility_ns_map_macos = _accessibility_ns_map["macos"]

    # A11y tree getter for Ubuntu
    MAX_DEPTH = 50
    MAX_WIDTH = 1024
    MAX_CALLS = 5000

    def _create_atspi_node(self, node: Accessible, depth: int = 0, flag: str | None = None) -> _Element:
        node_name = node.name
        attribute_dict: dict[str, Any] = {"name": node_name}

        #  States
        states: list[StateType] = node.getState().get_states()
        for st in states:
            state_name: str = StateType._enum_lookup[st]
            state_name: str = state_name.split("_", maxsplit=1)[1].lower()
            if len(state_name) == 0:
                continue
            attribute_dict["{{{:}}}{:}".format(_accessibility_ns_map_ubuntu["st"], state_name)] = "true"

        #  Attributes
        attributes: dict[str, str] = node.get_attributes()
        for attribute_name, attribute_value in attributes.items():
            if len(attribute_name) == 0:
                continue
            attribute_dict["{{{:}}}{:}".format(_accessibility_ns_map_ubuntu["attr"], attribute_name)] = attribute_value

        #  Component
        if (
            attribute_dict.get("{{{:}}}visible".format(_accessibility_ns_map_ubuntu["st"]), "false") == "true"
            and attribute_dict.get("{{{:}}}showing".format(_accessibility_ns_map_ubuntu["st"]), "false") == "true"
        ):
            try:
                component: Component = node.queryComponent()
            except NotImplementedError:
                pass
            else:
                bbox: Sequence[int] = component.getExtents(pyatspi.XY_SCREEN)
                attribute_dict["{{{:}}}screencoord".format(_accessibility_ns_map_ubuntu["cp"])] = str(tuple(bbox[0:2]))
                attribute_dict["{{{:}}}size".format(_accessibility_ns_map_ubuntu["cp"])] = str(tuple(bbox[2:]))

        text = ""
        #  Text
        try:
            text_obj: ATText = node.queryText()
            # only text shown on current screen is available
            # attribute_dict["txt:text"] = text_obj.getText(0, text_obj.characterCount)
            text: str = text_obj.getText(0, text_obj.characterCount)
            # if flag=="thunderbird":
            # appeared in thunderbird (uFFFC) (not only in thunderbird), "Object
            # Replacement Character" in Unicode, "used as placeholder in text for
            # an otherwise unspecified object; uFFFD is another "Replacement
            # Character", just in case
            text = text.replace("\ufffc", "").replace("\ufffd", "")
        except NotImplementedError:
            pass

        #  Image, Selection, Value, Action
        try:
            node.queryImage()
            attribute_dict["image"] = "true"
        except NotImplementedError:
            pass

        try:
            node.querySelection()
            attribute_dict["selection"] = "true"
        except NotImplementedError:
            pass

        try:
            value: ATValue = node.queryValue()
            value_key = f"{{{_accessibility_ns_map_ubuntu['val']}}}"

            for attr_name, attr_func in [
                ("value", lambda: value.currentValue),
                ("min", lambda: value.minimumValue),
                ("max", lambda: value.maximumValue),
                ("step", lambda: value.minimumIncrement),
            ]:
                try:
                    attribute_dict[f"{value_key}{attr_name}"] = str(attr_func())
                except:
                    pass
        except NotImplementedError:
            pass

        try:
            action: ATAction = node.queryAction()
            for i in range(action.nActions):
                action_name: str = action.getName(i).replace(" ", "-")
                attribute_dict["{{{:}}}{:}_desc".format(_accessibility_ns_map_ubuntu["act"], action_name)] = (
                    action.getDescription(i)
                )
                attribute_dict["{{{:}}}{:}_kb".format(_accessibility_ns_map_ubuntu["act"], action_name)] = (
                    action.getKeyBinding(i)
                )
        except NotImplementedError:
            pass

        # Add from here if we need more attributes in the future...

        raw_role_name: str = node.getRoleName().strip()
        node_role_name = (raw_role_name or "unknown").replace(" ", "-")

        if not flag:
            if raw_role_name == "document spreadsheet":
                flag = "calc"
            if raw_role_name == "application" and node.name == "Thunderbird":
                flag = "thunderbird"

        xml_node = lxml.etree.Element(node_role_name, attrib=attribute_dict, nsmap=_accessibility_ns_map_ubuntu)

        if len(text) > 0:
            xml_node.text = text

        if depth == self.MAX_DEPTH:
            self.logger.warning("Max depth reached")
            return xml_node

        if flag == "calc" and node_role_name == "table":
            # Maximum column: 1024 if ver<=7.3 else 16384
            # Maximum row: 104 8576
            # Maximun sheet: 1 0000

            MAXIMUN_COLUMN = 1024 if self.libreoffice_version_tuple < (7, 4) else 16384
            MAX_ROW = 104_8576

            index_base = 0
            first_showing = False
            column_base = None
            for r in range(MAX_ROW):
                for clm in range(column_base or 0, MAXIMUN_COLUMN):
                    child_node: Accessible = node[index_base + clm]
                    showing: bool = child_node.getState().contains(STATE_SHOWING)
                    if showing:
                        child_node: _Element = self._create_atspi_node(child_node, depth + 1, flag)
                        if not first_showing:
                            column_base = clm
                            first_showing = True
                        xml_node.append(child_node)
                    elif first_showing and column_base is not None or clm >= 500:
                        break
                if first_showing and clm == column_base or not first_showing and r >= 500:
                    break
                index_base += MAXIMUN_COLUMN
            return xml_node
        else:
            try:
                for i, ch in enumerate(node):
                    if i == self.MAX_WIDTH:
                        self.logger.warning("Max width reached")
                        break
                    xml_node.append(self._create_atspi_node(ch, depth + 1, flag))
            except:
                self.logger.warning(
                    "Error occurred during children traversing. Has Ignored. Node: %s",
                    lxml.etree.tostring(xml_node, encoding="unicode"),
                )
            return xml_node

    # A11y tree getter for Windows
    def _create_pywinauto_node(self, node, nodes, depth: int = 0, flag: str | None = None) -> _Element:
        nodes = nodes or set()
        if node in nodes:
            return
        nodes.add(node)

        attribute_dict: dict[str, Any] = {"name": node.element_info.name}

        base_properties = {}
        try:
            base_properties.update(
                node.get_properties()
            )  # get all writable/not writable properties, but have bugs when landing on chrome and it's slower!
        except:
            self.logger.debug("Failed to call get_properties(), trying to get writable properites")
            try:
                _element_class = node.__class__

                class TempElement(node.__class__):
                    writable_props = pywinauto.base_wrapper.BaseWrapper.writable_props

                # Instantiate the subclass
                node.__class__ = TempElement
                # Retrieve properties using get_properties()
                properties = node.get_properties()
                node.__class__ = _element_class

                base_properties.update(properties)  # only get all writable properties
                self.logger.debug("get writable properties")
            except Exception as e:
                self.logger.error(e)
                pass

        # Count-cnt
        for attr_name in ["control_count", "button_count", "item_count", "column_count"]:
            try:
                attribute_dict[f"{{{_accessibility_ns_map_windows['cnt']}}}{attr_name}"] = base_properties[
                    attr_name
                ].lower()
            except:
                pass

        # Columns-cols
        try:
            attribute_dict[f"{{{_accessibility_ns_map_windows['cols']}}}columns"] = base_properties["columns"].lower()
        except:
            pass

        # Id-id
        for attr_name in ["control_id", "automation_id", "window_id"]:
            try:
                attribute_dict[f"{{{_accessibility_ns_map_windows['id']}}}{attr_name}"] = base_properties[attr_name].lower()
            except:
                pass

        #  States
        # 19 sec out of 20
        for attr_name, attr_func in [
            ("enabled", lambda: node.is_enabled()),
            ("visible", lambda: node.is_visible()),
            # ("active", lambda: node.is_active()), # occupied most of the time: 20s out of 21s for slack, 51.5s out of 54s for WeChat # maybe use for cutting branches
            ("minimized", lambda: node.is_minimized()),
            ("maximized", lambda: node.is_maximized()),
            ("normal", lambda: node.is_normal()),
            ("unicode", lambda: node.is_unicode()),
            ("collapsed", lambda: node.is_collapsed()),
            ("checkable", lambda: node.is_checkable()),
            ("checked", lambda: node.is_checked()),
            ("focused", lambda: node.is_focused()),
            ("keyboard_focused", lambda: node.is_keyboard_focused()),
            ("selected", lambda: node.is_selected()),
            ("selection_required", lambda: node.is_selection_required()),
            ("pressable", lambda: node.is_pressable()),
            ("pressed", lambda: node.is_pressed()),
            ("expanded", lambda: node.is_expanded()),
            ("editable", lambda: node.is_editable()),
            ("has_keyboard_focus", lambda: node.has_keyboard_focus()),
            ("is_keyboard_focusable", lambda: node.is_keyboard_focusable()),
        ]:
            try:
                attribute_dict[f"{{{_accessibility_ns_map_windows['st']}}}{attr_name}"] = str(attr_func()).lower()
            except:
                pass

        #  Component
        try:
            rectangle = node.rectangle()
            attribute_dict["{{{:}}}screencoord".format(_accessibility_ns_map_windows["cp"])] = "({:d}, {:d})".format(
                rectangle.left, rectangle.top
            )
            attribute_dict["{{{:}}}size".format(_accessibility_ns_map_windows["cp"])] = "({:d}, {:d})".format(
                rectangle.width(), rectangle.height()
            )

        except Exception as e:
            self.logger.error("Error accessing rectangle: ", e)

        #  Text
        text: str = node.window_text()
        if text == attribute_dict["name"]:
            text = ""

        #  Selection
        if hasattr(node, "select"):
            attribute_dict["selection"] = "true"

        # Value
        for attr_name, attr_funcs in [
            ("step", [lambda: node.get_step()]),
            ("value", [lambda: node.value(), lambda: node.get_value(), lambda: node.get_position()]),
            ("min", [lambda: node.min_value(), lambda: node.get_range_min()]),
            ("max", [lambda: node.max_value(), lambda: node.get_range_max()]),
        ]:
            for attr_func in attr_funcs:
                if hasattr(node, attr_func.__name__):
                    try:
                        attribute_dict[f"{{{_accessibility_ns_map_windows['val']}}}{attr_name}"] = str(attr_func())
                        break  # exit once the attribute is set successfully
                    except:
                        pass

        attribute_dict["{{{:}}}class".format(_accessibility_ns_map_windows["class"])] = str(type(node))

        # class_name
        for attr_name in ["class_name", "friendly_class_name"]:
            try:
                attribute_dict[f"{{{_accessibility_ns_map_windows['class']}}}{attr_name}"] = base_properties[
                    attr_name
                ].lower()
            except:
                pass

        node_role_name: str = node.class_name().lower().replace(" ", "-")
        node_role_name = "".join(
            map(lambda _ch: _ch if _ch.isidentifier() or _ch in {"-"} or _ch.isalnum() else "-", node_role_name)
        )

        if node_role_name.strip() == "":
            node_role_name = "unknown"
        if not node_role_name[0].isalpha():
            node_role_name = "tag" + node_role_name

        xml_node = lxml.etree.Element(node_role_name, attrib=attribute_dict, nsmap=_accessibility_ns_map_windows)

        if text is not None and len(text) > 0 and text != attribute_dict["name"]:
            xml_node.text = text

        if depth == self.MAX_DEPTH:
            self.logger.warning("Max depth reached")
            return xml_node

        # use multi thread to accelerate children fetching
        children = node.children()
        if children:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_child = [
                    executor.submit(self._create_pywinauto_node, ch, nodes, depth + 1, flag) for ch in children[:self.MAX_WIDTH]
                ]
            try:
                xml_node.extend([future.result() for future in concurrent.futures.as_completed(future_to_child)])
            except Exception as e:
                self.logger.error(f"Exception occurred: {e}")
        return xml_node

    # A11y tree getter for macOS

    def _create_axui_node(self, node, nodes: set = None, depth: int = 0, bbox: tuple = None):
        nodes = nodes or set()
        if node in nodes:
            return
        nodes.add(node)

        reserved_keys = {
            "AXEnabled": "st",
            "AXFocused": "st",
            "AXFullScreen": "st",
            "AXTitle": "attr",
            "AXChildrenInNavigationOrder": "attr",
            "AXChildren": "attr",
            "AXFrame": "attr",
            "AXRole": "role",
            "AXHelp": "attr",
            "AXRoleDescription": "role",
            "AXSubrole": "role",
            "AXURL": "attr",
            "AXValue": "val",
            "AXDescription": "attr",
            "AXDOMIdentifier": "attr",
            "AXSelected": "st",
            "AXInvalid": "st",
            "AXRows": "attr",
            "AXColumns": "attr",
        }
        attribute_dict = {}

        if depth == 0:
            bbox = (
                node["kCGWindowBounds"]["X"],
                node["kCGWindowBounds"]["Y"],
                node["kCGWindowBounds"]["X"] + node["kCGWindowBounds"]["Width"],
                node["kCGWindowBounds"]["Y"] + node["kCGWindowBounds"]["Height"],
            )
            app_ref = ApplicationServices.AXUIElementCreateApplication(node["kCGWindowOwnerPID"])

            attribute_dict["name"] = node["kCGWindowOwnerName"]
            if attribute_dict["name"] != "Dock":
                error_code, app_wins_ref = ApplicationServices.AXUIElementCopyAttributeValue(app_ref, "AXWindows", None)
                if error_code:
                    self.logger.error("MacOS parsing %s encountered Error code: %d", app_ref, error_code)
            else:
                app_wins_ref = [app_ref]
            node = app_wins_ref[0]

        error_code, attr_names = ApplicationServices.AXUIElementCopyAttributeNames(node, None)

        if error_code:
            # -25202: AXError.invalidUIElement
            #         The accessibility object received in this event is invalid.
            return

        value = None

        if "AXFrame" in attr_names:
            error_code, attr_val = ApplicationServices.AXUIElementCopyAttributeValue(node, "AXFrame", None)
            rep = repr(attr_val)
            x_value = re.search(r"x:(-?[\d.]+)", rep)
            y_value = re.search(r"y:(-?[\d.]+)", rep)
            w_value = re.search(r"w:(-?[\d.]+)", rep)
            h_value = re.search(r"h:(-?[\d.]+)", rep)
            type_value = re.search(r"type\s?=\s?(\w+)", rep)
            value = {
                "x": float(x_value.group(1)) if x_value else None,
                "y": float(y_value.group(1)) if y_value else None,
                "w": float(w_value.group(1)) if w_value else None,
                "h": float(h_value.group(1)) if h_value else None,
                "type": type_value.group(1) if type_value else None,
            }

            if not any(v is None for v in value.values()):
                x_min = max(bbox[0], value["x"])
                x_max = min(bbox[2], value["x"] + value["w"])
                y_min = max(bbox[1], value["y"])
                y_max = min(bbox[3], value["y"] + value["h"])

                if x_min > x_max or y_min > y_max:
                    # No intersection
                    return

        role = None
        text = None

        for attr_name, ns_key in reserved_keys.items():
            if attr_name not in attr_names:
                continue

            if value and attr_name == "AXFrame":
                bb = value
                if not any(v is None for v in bb.values()):
                    attribute_dict["{{{:}}}screencoord".format(_accessibility_ns_map_macos["cp"])] = "({:d}, {:d})".format(
                        int(bb["x"]), int(bb["y"])
                    )
                    attribute_dict["{{{:}}}size".format(_accessibility_ns_map_macos["cp"])] = "({:d}, {:d})".format(
                        int(bb["w"]), int(bb["h"])
                    )
                continue

            error_code, attr_val = ApplicationServices.AXUIElementCopyAttributeValue(node, attr_name, None)

            full_attr_name = f"{{{_accessibility_ns_map_macos[ns_key]}}}{attr_name}"

            if attr_name == "AXValue" and not text:
                text = str(attr_val)
                continue

            if attr_name == "AXRoleDescription":
                role = attr_val
                continue

            # Set the attribute_dict
            if not (
                isinstance(attr_val, ApplicationServices.AXUIElementRef) or isinstance(attr_val, (AppKit.NSArray, list))
            ):
                if attr_val is not None:
                    attribute_dict[full_attr_name] = str(attr_val)

        node_role_name = role.lower().replace(" ", "_") if role else "unknown_role"

        xml_node = lxml.etree.Element(node_role_name, attrib=attribute_dict, nsmap=_accessibility_ns_map_macos)

        if text is not None and len(text) > 0:
            xml_node.text = text

        if depth == self.MAX_DEPTH:
            self.logger.warning("Max depth reached")
            return xml_node

        future_to_child = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for attr_name, ns_key in reserved_keys.items():
                if attr_name not in attr_names:
                    continue

                error_code, attr_val = ApplicationServices.AXUIElementCopyAttributeValue(node, attr_name, None)
                if isinstance(attr_val, ApplicationServices.AXUIElementRef):
                    future_to_child.append(executor.submit(self._create_axui_node, attr_val, nodes, depth + 1, bbox))

                elif isinstance(attr_val, (AppKit.NSArray, list)):
                    for child in attr_val:
                        future_to_child.append(executor.submit(self._create_axui_node, child, nodes, depth + 1, bbox))

            try:
                for future in concurrent.futures.as_completed(future_to_child):
                    result = future.result()
                    if result is not None:
                        xml_node.append(result)
            except Exception as e:
                self.logger.error(f"Exception occurred: {e}")

        return xml_node

    async def get_accessibility_tree(self):
        os_name: str = platform.system()

        # AT-SPI works for KDE as well
        if os_name == "Linux":

            desktop: Accessible = pyatspi.Registry.getDesktop(0)
            xml_node = lxml.etree.Element("desktop-frame", nsmap=_accessibility_ns_map_ubuntu)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self._create_atspi_node, app_node, 1) for app_node in desktop]
                for future in concurrent.futures.as_completed(futures):
                    xml_tree = future.result()
                    xml_node.append(xml_tree)
            return AccessibilityTreeResponse(at=lxml.etree.tostring(xml_node, encoding="unicode"))

        elif os_name == "Windows":
            # Attention: Windows a11y tree is implemented to be read through `pywinauto` module, however,
            # two different backends `win32` and `uia` are supported and different results may be returned
            desktop: Desktop = Desktop(backend="uia")
            xml_node = lxml.etree.Element("desktop", nsmap=_accessibility_ns_map_windows)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self._create_pywinauto_node, wnd, {}, 1) for wnd in desktop.windows()]
                for future in concurrent.futures.as_completed(futures):
                    xml_tree = future.result()
                    xml_node.append(xml_tree)
            return AccessibilityTreeResponse(at=lxml.etree.tostring(xml_node, encoding="unicode"))

        elif os_name == "Darwin":
            # TODO: Add Dock and MenuBar
            xml_node = lxml.etree.Element("desktop", nsmap=_accessibility_ns_map_macos)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                foreground_windows = [
                    win
                    for win in Quartz.CGWindowListCopyWindowInfo(
                        (Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly),
                        Quartz.kCGNullWindowID,
                    )
                    if win["kCGWindowLayer"] == 0 and win["kCGWindowOwnerName"] != "Window Server"
                ]
                dock_info = [
                    win
                    for win in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
                    if win.get("kCGWindowName", None) == "Dock"
                ]

                futures = [executor.submit(self._create_axui_node, wnd, None, 0) for wnd in foreground_windows + dock_info]

                for future in concurrent.futures.as_completed(futures):
                    xml_tree = future.result()
                    if xml_tree is not None:
                        xml_node.append(xml_tree)

            return AccessibilityTreeResponse(at=lxml.etree.tostring(xml_node, encoding="unicode"))

        else:
            raise HTTPException(status_code=501, detail=f"Currently not implemented for platform {platform.platform()}.")

    async def get_screen_size(self) -> ScreenSizeResponse:
        if platform_name == "Linux":
            d = display.Display()
            screen_width = d.screen().width_in_pixels
            screen_height = d.screen().height_in_pixels
        elif platform_name == "Windows":
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
        return ScreenSizeResponse(
            width=screen_width,
            height=screen_height,
        )

    async def get_window_size(self, request: WindowSizeRequest) -> Optional[WindowSizeResponse]:
        d = display.Display()
        root = d.screen().root
        window_ids = root.get_full_property(d.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType).value

        for window_id in window_ids:
            try:
                window = d.create_resource_object("window", window_id)
                wm_class = window.get_wm_class()

                if wm_class is None:
                    continue

                if request.app_class_name.lower() in [name.lower() for name in wm_class]:
                    geom = window.get_geometry()
                    return WindowSizeResponse(width=geom.width, height=geom.height)
            except Xlib.error.XError:  # Ignore windows that give an error
                continue
        return None

    async def get_desktop_path(self) -> DesktopPathResponse:
        # Get the home directory in a platform-independent manner using pathlib
        home_directory = str(Path.home())

        # Determine the desktop path based on the operating system
        desktop_path = {
            "Windows": os.path.join(home_directory, "Desktop"),
            "Darwin": os.path.join(home_directory, "Desktop"),  # macOS
            "Linux": os.path.join(home_directory, "Desktop"),
        }.get(platform.system(), None)

        # Check if the operating system is supported and the desktop path exists
        if desktop_path and os.path.exists(desktop_path):
            return DesktopPathResponse(
                desktop_path=desktop_path,
                is_writable=os.access(desktop_path, os.W_OK)
            )
        else:
            raise HTTPException(status_code=404, detail="Unsupported operating system or desktop path not found")

    async def get_wallpaper(self):
        def get_wallpaper_windows():
            SPI_GETDESKWALLPAPER = 0x73
            MAX_PATH = 260
            buffer = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, MAX_PATH, buffer, 0)
            return buffer.value

        def get_wallpaper_macos():
            script = """
            tell application "System Events" to tell every desktop to get picture
            """
            process = subprocess.Popen(["osascript", "-e", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = process.communicate()
            if error:
                self.logger.error("Error: %s", error.decode("utf-8"))
                return None
            return output.strip().decode("utf-8")

        def get_wallpaper_linux():
            try:
                output = subprocess.check_output(
                    ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"], stderr=subprocess.PIPE
                )
                return output.decode("utf-8").strip().replace("file://", "").replace("'", "")
            except subprocess.CalledProcessError as e:
                self.logger.error("Error: %s", e)
                return None

        os_name = platform.system()
        wallpaper_path = None
        if os_name == "Windows":
            wallpaper_path = get_wallpaper_windows()
        elif os_name == "Darwin":
            wallpaper_path = get_wallpaper_macos()
        elif os_name == "Linux":
            wallpaper_path = get_wallpaper_linux()
        else:
            self.logger.error(f"Unsupported OS: {os_name}")
            raise HTTPException(status_code=400, detail="Unsupported OS")

        if wallpaper_path:
            try:
                # Ensure the filename is secure
                return FileResponse(wallpaper_path, media_type="image/png")
            except Exception as e:
                self.logger.error(f"An error occurred while serving the wallpaper file: {e}")
                raise HTTPException(status_code=500, detail="Unable to serve the wallpaper file")
        else:
            raise HTTPException(status_code=404, detail="Wallpaper file not found")

    async def get_directory_tree(self, request: DirectoryRequest) -> DirectoryTreeResponse:
        def _list_dir_contents(directory):
            """
            List the contents of a directory recursively, building a tree structure.

            :param directory: The path of the directory to inspect.
            :return: A nested dictionary with the contents of the directory.
            """
            tree = {"type": "directory", "name": os.path.basename(directory), "children": []}
            try:
                # List all files and directories in the current directory
                for entry in os.listdir(directory):
                    full_path = os.path.join(directory, entry)
                    # If entry is a directory, recurse into it
                    if os.path.isdir(full_path):
                        tree["children"].append(_list_dir_contents(full_path))
                    else:
                        tree["children"].append({"type": "file", "name": entry})
            except OSError as e:
                # If the directory cannot be accessed, return the exception message
                tree = {"error": str(e)}
            return tree

        start_path = request.path
        # Ensure the provided path is a directory
        if not os.path.isdir(start_path):
            raise HTTPException(status_code=400, detail="The provided path is not a directory")

        # Generate the directory tree starting from the provided path
        directory_tree = _list_dir_contents(start_path)
        return DirectoryTreeResponse(directory_tree=directory_tree)

    async def get_file(self, request: FileRequest):
        try:
            # Check if the file exists and send it to the user
            return FileResponse(request.file_path, as_attachment=True)
        except FileNotFoundError:
            # If the file is not found, return a 404 error
            raise HTTPException(status_code=404, detail="File not found")

    async def upload_file(self, file_path: str = Form(...), file_data: UploadFile = File(...)):
        try:
            file_path = os.path.expandvars(os.path.expanduser(file_path))
            with open(file_path, "wb") as f:
                content = await file_data.read()
                f.write(content)
            return "File Uploaded"
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def get_platform(self) -> PlatformResponse:
        return PlatformResponse(
            platform=platform.system(),
            version=platform.version(),
            architecture=platform.machine(),
            machine=platform.processor()
        )

    async def get_cursor_position(self) -> CursorPositionResponse:
        pos = pyautogui.position()
        return CursorPositionResponse(
            x=pos.x,
            y=pos.y,
            screen=0  # TODO: Implement multi-monitor support
        )

    async def change_wallpaper(self, request: WallpaperRequest):
        if not request.path:
            raise HTTPException(status_code=400, detail="Path not supplied!")

        path = Path(os.path.expandvars(os.path.expanduser(request.path)))

        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        try:
            user_platform = platform.system()
            if user_platform == "Windows":
                import ctypes
                ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
            elif user_platform == "Linux":
                import subprocess
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"])
            elif user_platform == "Darwin":  # (Mac OS)
                import subprocess
                subprocess.run(
                    ["osascript", "-e", f'tell application "Finder" to set desktop picture to POSIX file "{path}"']
                )
            return "Wallpaper changed successfully"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to change wallpaper. Error: {e}")

    
    async def download_file(self, request: DownloadRequest):
        if not request.url or not request.path:
            raise HTTPException(status_code=400, detail="Path or URL not supplied!")

        path = Path(os.path.expandvars(os.path.expanduser(request.path)))
        path.parent.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        error: Exception | None = None
        for i in range(max_retries):
            try:
                response = requests.get(request.url, stream=True)
                response.raise_for_status()

                with open(path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return "File downloaded successfully"

            except requests.RequestException as e:
                error = e
                self.logger.error(f"Failed to download {request.url}. Retrying... ({max_retries - i - 1} attempts left)")

        raise HTTPException(status_code=500, detail=f"Failed to download {request.url}. No retries left. Error: {error}")

    async def open_file(self, request: OpenFileRequest):
        if not request.path:
            raise HTTPException(status_code=400, detail="Path not supplied!")

        path = Path(os.path.expandvars(os.path.expanduser(request.path)))

        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        try:
            if platform.system() == "Windows":
                os.startfile(path)
            else:
                open_cmd: str = "open" if platform.system() == "Darwin" else "xdg-open"
                subprocess.Popen([open_cmd, str(path)])
            return "File opened successfully"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open {path}. Error: {e}")

    async def activate_window(self, request: WindowRequest):
        if not request.window_name:
            raise HTTPException(status_code=400, detail="window_name required")

        os_name = platform.system()

        if os_name == "Windows":
            import pygetwindow as gw

            if request.by_class:
                raise HTTPException(status_code=500, detail="Get window by class name is not supported on Windows currently.")
            windows: list[gw.Window] = gw.getWindowsWithTitle(request.window_name)

            window: gw.Window | None = None
            if len(windows) == 0:
                raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (empty results)")
            elif request.strict:
                for wnd in windows:
                    if wnd.title == wnd:
                        window = wnd
                if window is None:
                    raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (strict mode).")
            else:
                window = windows[0]
            window.activate()

        elif os_name == "Darwin":
            import pygetwindow as gw

            if request.by_class:
                raise HTTPException(status_code=500, detail="Get window by class name is not supported on macOS currently.")
            # Find the VS Code window
            windows = gw.getWindowsWithTitle(request.window_name)

            window: gw.Window | None = None
            if len(windows) == 0:
                raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (empty results)")
            elif request.strict:
                for wnd in windows:
                    if wnd.title == wnd:
                        window = wnd
                if window is None:
                    raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (strict mode).")
            else:
                window = windows[0]

            # Un-minimize the window and then bring it to the front
            window.unminimize()
            window.activate()

        elif os_name == "Linux":
            # Attempt to activate VS Code window using wmctrl
            subprocess.run(["wmctrl", "-{:}{:}a".format("x" if request.by_class else "", "F" if request.strict else ""), request.window_name])

        else:
            raise HTTPException(status_code=400, detail=f"Operating system {os_name} not supported.")

        return "Window activated successfully"

    async def close_window(self, request: WindowRequest):
        if not request.window_name:
            raise HTTPException(status_code=400, detail="window_name required")

        os_name: str = platform.system()
        if os_name == "Windows":
            import pygetwindow as gw

            if request.by_class:
                raise HTTPException(status_code=500, detail="Get window by class name is not supported on Windows currently.")
            windows: list[gw.Window] = gw.getWindowsWithTitle(request.window_name)

            window: gw.Window | None = None
            if len(windows) == 0:
                raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (empty results)")
            elif request.strict:
                for wnd in windows:
                    if wnd.title == wnd:
                        window = wnd
                if window is None:
                    raise HTTPException(status_code=404, detail=f"Window {request.window_name} not found (strict mode).")
            else:
                window = windows[0]
            window.close()
        elif os_name == "Linux":
            subprocess.run(["wmctrl", "-{:}{:}c".format("x" if request.by_class else "", "F" if request.strict else ""), request.window_name])
        elif os_name == "Darwin":
            import pygetwindow as gw
            raise HTTPException(status_code=500, detail="Currently not supported on macOS.")
        else:
            raise HTTPException(status_code=500, detail=f"Not supported platform {os_name}")

    async def start_recording(self, app: FastAPI) -> RecordingResponse:
        if app.state.recording_process:
            raise HTTPException(status_code=400, detail="Recording is already in progress.")

        d = display.Display()
        screen_width = d.screen().width_in_pixels
        screen_height = d.screen().height_in_pixels

        start_command = f"ffmpeg -y -f x11grab -draw_mouse 1 -s {screen_width}x{screen_height} -i :0.0 -c:v libx264 -r 30 {app.state.recording_path}"

        app.state.recording_process = subprocess.Popen(
            shlex.split(start_command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        return RecordingResponse(
            path=app.state.recording_path,
            format="mp4",
            message="Recording started successfully"
        )

    async def end_recording(self, app: FastAPI) -> RecordingResponse:
        if not app.state.recording_process:
            raise HTTPException(status_code=400, detail="No recording in progress to stop.")

        app.state.recording_process.send_signal(signal.SIGINT)
        app.state.recording_process.wait()
        app.state.recording_process = None

        # return recording video file
        if os.path.exists(app.state.recording_path):
            size = os.path.getsize(app.state.recording_path)
            return RecordingResponse(
                path=app.state.recording_path,
                format="mp4",
                size=size,
                message="Recording completed successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Recording failed")

if __name__ == "__main__":
    import uvicorn
    server = DesktopServer()
    uvicorn.run(server.app, host="0.0.0.0", port=8000)
