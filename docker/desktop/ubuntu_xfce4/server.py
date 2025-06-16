# inspired by: https://github.com/xlang-ai/OSWorld/blob/main/desktop_env/server/main.py

import concurrent.futures
import os
import platform
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Sequence, Union

import lxml.etree
import pyatspi
import pyautogui
import requests
import Xlib
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from lxml.etree import _Element
from pyatspi import (
    STATE_SHOWING,
    Accessible,
    Component,  # , Document
    StateType,
)
from pyatspi import Action as ATAction
from pyatspi import Text as ATText
from pyatspi import Value as ATValue
from Xlib import X, display

from ..base_server import BaseServer
from ..request_models import (
    CommandRequest,
    DirectoryRequest,
    DownloadRequest,
    FileRequest,
    WindowRequest,
    WindowSizeRequest,
)
from ..response_models import (
    AccessibilityTreeResponse,
    BaseResponse,
    CommandResponse,
    CursorPositionResponse,
    DesktopPathResponse,
    DirectoryTreeResponse,
    PlatformResponse,
    RecordingResponse,
    ScreenSizeResponse,
    StatusEnum,
    TerminalOutputResponse,
    WindowInfoResponse,
    WindowListResponse,
    WindowSizeResponse,
)

pyautogui.PAUSE = 0
pyautogui.DARWIN_CATCH_UP_TIME = 0

BaseWrapper = Any


class UbuntuXfce4Server(BaseServer):
    def __init__(self):
        super().__init__()
        self.recording_path = "/tmp/recording.mp4"
        # self.libreoffice_version_tuple = self._get_libreoffice_version()
        self.libreoffice_version_tuple = None
        self.MAX_DEPTH = 50
        self.MAX_WIDTH = 1024
        self.MAX_CALLS = 5000
        self._accessibility_ns_map_ubuntu = {
            "st": "https://accessibility.ubuntu.example.org/ns/state",
            "attr": "https://accessibility.ubuntu.example.org/ns/attributes",
            "cp": "https://accessibility.ubuntu.example.org/ns/component",
            "doc": "https://accessibility.ubuntu.example.org/ns/document",
            "docattr": "https://accessibility.ubuntu.example.org/ns/document/attributes",
            "txt": "https://accessibility.ubuntu.example.org/ns/text",
            "val": "https://accessibility.ubuntu.example.org/ns/value",
            "act": "https://accessibility.ubuntu.example.org/ns/action",
        }

        # Configure pyautogui
        pyautogui.PAUSE = 0
        pyautogui.DARWIN_CATCH_UP_TIME = 0

        # MOUSE_BUTTONS and KEYS are used in GUI operations
        self.MOUSE_BUTTONS = {"left": 1, "right": 3, "middle": 2}

        self.KEYS = {
            "alt": "Alt_L",
            "alt_left": "Alt_L",
            "alt_right": "Alt_R",
            "backspace": "BackSpace",
            "break": "Pause",
            "caps_lock": "Caps_Lock",
            "cmd": "Super_L",
            "command": "Super_L",
            "control": "Control_L",
            "control_left": "Control_L",
            "control_right": "Control_R",
            "ctrl": "Control_L",
            "del": "Delete",
            "delete": "Delete",
            "down": "Down",
            "end": "End",
            "enter": "Return",
            "esc": "Escape",
            "escape": "Escape",
            "f1": "F1",
            "f2": "F2",
            "f3": "F3",
            "f4": "F4",
            "f5": "F5",
            "f6": "F6",
            "f7": "F7",
            "f8": "F8",
            "f9": "F9",
            "f10": "F10",
            "f11": "F11",
            "f12": "F12",
            "home": "Home",
            "insert": "Insert",
            "left": "Left",
            "menu": "Menu",
            "meta": "Meta_L",
            "num_lock": "Num_Lock",
            "page_down": "Page_Down",
            "page_up": "Page_Up",
            "pause": "Pause",
            "print": "Print",
            "right": "Right",
            "scroll_lock": "Scroll_Lock",
            "shift": "Shift_L",
            "shift_left": "Shift_L",
            "shift_right": "Shift_R",
            "space": "space",
            "super": "Super_L",
            "super_left": "Super_L",
            "super_right": "Super_R",
            "tab": "Tab",
            "up": "Up",
            "win": "Super_L",
            "windows": "Super_L",
        }

    def _get_libreoffice_version(self) -> tuple[int, ...]:
        result = subprocess.run(
            "libreoffice --version", shell=True, text=True, stdout=subprocess.PIPE
        )
        version_str = result.stdout.split()[1]
        return tuple(map(int, version_str.split(".")))

    def _map_key(self, key: str) -> str:
        lower_key = key.lower()
        if lower_key in self.KEYS:
            return self.KEYS[lower_key]
        return lower_key

    async def execute_command(
        self, request: CommandRequest, retry_times: int = 3
    ) -> CommandResponse:
        command = request.command
        shell = request.shell
        background = request.background
        timeout = request.timeout

        assert isinstance(command, list)

        if command[-1] == "&":
            background = True
            command = command[:-1]

        for i, arg in enumerate(command):
            if arg.startswith("~/"):
                command[i] = os.path.expanduser(arg)

        flags = 0

        for i in range(retry_times):
            try:
                if background:
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=shell,
                        text=True,
                        creationflags=flags,
                    )
                    return CommandResponse(
                        status=StatusEnum.SUCCESS,
                        message="Command started in background",
                        output="",
                        error="",
                        returncode=0,
                    )
                else:
                    result = subprocess.run(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=shell,
                        text=True,
                        timeout=timeout,
                        creationflags=flags,
                    )
                    return CommandResponse(
                        status=StatusEnum.SUCCESS,
                        message="Command executed successfully",
                        output=result.stdout,
                        error=result.stderr,
                        returncode=result.returncode,
                    )
            except Exception as e:
                self.logger.error("Failed to execute command. Error: %s", e)
                self.logger.info("Retrying to execute command.")
                if i >= retry_times - 1:
                    break
            time.sleep(i)
        return CommandResponse(
            status=StatusEnum.ERROR,
            message="Failed to execute command.",
            output="",
            error="",
            returncode=1,
        )

    def _get_machine_architecture(self) -> str:
        architecture = platform.machine().lower()
        if architecture in [
            "amd32",
            "amd64",
            "x86",
            "x86_64",
            "x86-64",
            "x64",
            "i386",
            "i686",
        ]:
            return "amd"
        elif architecture in ["arm64", "aarch64", "aarch32"]:
            return "arm"
        else:
            return "unknown"

    # async def capture_screen_with_cursor(self):
    #     file_path = os.path.join(os.path.dirname(__file__), "screenshots", "screenshot.png")

    #     os.makedirs(os.path.dirname(file_path), exist_ok=True)
    #     cursor_obj = Xcursor()
    #     imgarray = cursor_obj.getCursorImageArrayFast()
    #     cursor_img = Image.fromarray(imgarray)
    #     screenshot = pyautogui.screenshot()
    #     cursor_x, cursor_y = pyautogui.position()
    #     screenshot.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
    #     screenshot.save(file_path)

    #     return FileResponse(file_path, media_type="image/png")

    def _has_active_terminal(self, desktop: Accessible) -> bool:
        """A quick check whether the terminal window is open and active."""
        for app in desktop:
            if app.getRoleName() == "application" and app.name == "xfce4-terminal":
                for frame in app:
                    if frame.getRoleName() == "frame" and frame.getState().contains(
                        pyatspi.STATE_ACTIVE
                    ):
                        return True
        return False

    async def get_terminal_output(self):
        output: str | None = None
        try:
            desktop: Accessible = pyatspi.Registry.getDesktop(0)
            if self._has_active_terminal(desktop):
                desktop_xml: _Element = self._create_atspi_node(desktop)
                # 1. the terminal window (frame of application is st:active) is open and active
                # 2. the terminal tab (terminal status is st:focused) is focused
                xpath = '//application[@name="xfce4-terminal"]/frame[@st:active="true"]//terminal[@st:focused="true"]'
                terminals: list[_Element] = desktop_xml.xpath(
                    xpath, namespaces=self._accessibility_ns_map_ubuntu
                )
                output = terminals[0].text.rstrip() if len(terminals) == 1 else None
            return TerminalOutputResponse(output=output, status="success")
        except Exception as e:
            self.logger.error("Failed to get terminal output. Error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    def _create_atspi_node(
        self, node: Accessible, depth: int = 0, flag: str | None = None
    ) -> _Element:
        node_name = node.name
        attribute_dict: dict[str, Any] = {"name": node_name}

        #  States
        states: list[StateType] = node.getState().get_states()
        for st in states:
            state_name: str = StateType._enum_lookup[st]
            state_name: str = state_name.split("_", maxsplit=1)[1].lower()
            if len(state_name) == 0:
                continue
            attribute_dict[
                "{{{:}}}{:}".format(self._accessibility_ns_map_ubuntu["st"], state_name)
            ] = "true"

        #  Attributes
        attributes: dict[str, str] = node.get_attributes()
        for attribute_name, attribute_value in attributes.items():
            if len(attribute_name) == 0:
                continue
            attribute_dict[
                "{{{:}}}{:}".format(
                    self._accessibility_ns_map_ubuntu["attr"], attribute_name
                )
            ] = attribute_value

        #  Component
        if (
            attribute_dict.get(
                "{{{:}}}visible".format(self._accessibility_ns_map_ubuntu["st"]),
                "false",
            )
            == "true"
            and attribute_dict.get(
                "{{{:}}}showing".format(self._accessibility_ns_map_ubuntu["st"]),
                "false",
            )
            == "true"
        ):
            try:
                component: Component = node.queryComponent()
            except NotImplementedError:
                pass
            else:
                bbox: Sequence[int] = component.getExtents(pyatspi.XY_SCREEN)
                attribute_dict[
                    "{{{:}}}screencoord".format(self._accessibility_ns_map_ubuntu["cp"])
                ] = str(tuple(bbox[0:2]))
                attribute_dict[
                    "{{{:}}}size".format(self._accessibility_ns_map_ubuntu["cp"])
                ] = str(tuple(bbox[2:]))

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
            value_key = f"{{{self._accessibility_ns_map_ubuntu['val']}}}"

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
                attribute_dict[
                    "{{{:}}}{:}_desc".format(
                        self._accessibility_ns_map_ubuntu["act"], action_name
                    )
                ] = action.getDescription(i)
                attribute_dict[
                    "{{{:}}}{:}_kb".format(
                        self._accessibility_ns_map_ubuntu["act"], action_name
                    )
                ] = action.getKeyBinding(i)
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

        xml_node = lxml.etree.Element(
            node_role_name,
            attrib=attribute_dict,
            nsmap=self._accessibility_ns_map_ubuntu,
        )

        if len(text) > 0:
            xml_node.text = text

        if depth == self.MAX_DEPTH:
            self.logger.warning("Max depth reached")
            return xml_node

        if flag == "calc" and node_role_name == "table":
            # Maximum column: 1024 if ver<=7.3 else 16384
            # Maximum row: 104 8576
            # Maximun sheet: 1 0000

            if self.libreoffice_version_tuple is None:
                self.libreoffice_version_tuple = self._get_libreoffice_version()
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
                        child_node: _Element = self._create_atspi_node(
                            child_node, depth + 1, flag
                        )
                        if not first_showing:
                            column_base = clm
                            first_showing = True
                        xml_node.append(child_node)
                    elif first_showing and column_base is not None or clm >= 500:
                        break
                if (
                    first_showing
                    and clm == column_base
                    or not first_showing
                    and r >= 500
                ):
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

    async def get_accessibility_tree(self):
        try:
            if self.libreoffice_version_tuple is None:
                self.libreoffice_version_tuple = self._get_libreoffice_version()
            desktop: Accessible = pyatspi.Registry.getDesktop(0)
            xml_node = lxml.etree.Element(
                "desktop-frame", nsmap=self._accessibility_ns_map_ubuntu
            )
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self._create_atspi_node, app_node, 1)
                    for app_node in desktop
                ]
                for future in concurrent.futures.as_completed(futures):
                    xml_tree = future.result()
                    xml_node.append(xml_tree)
            return AccessibilityTreeResponse(
                at=lxml.etree.tostring(xml_node, encoding="unicode")
            )
        except Exception as e:
            self.logger.error("Failed to get accessibility tree. Error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_window_size(
        self, request: WindowSizeRequest
    ) -> WindowSizeResponse | None:
        d = display.Display()
        root = d.screen().root
        window_ids = root.get_full_property(
            d.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType
        ).value

        for window_id in window_ids:
            try:
                window = d.create_resource_object("window", window_id)
                wm_class = window.get_wm_class()

                if wm_class is None:
                    continue

                if request.app_class_name.lower() in [
                    name.lower() for name in wm_class
                ]:
                    geom = window.get_geometry()
                    return WindowSizeResponse(width=geom.width, height=geom.height)
            except Xlib.error.XError:  # Ignore windows that give an error
                continue
        return None

    async def get_desktop_path(self) -> DesktopPathResponse:
        # Get the home directory in a platform-independent manner using pathlib
        home_directory = str(Path.home())

        # Determine the desktop path based on the operating system
        desktop_path = os.path.join(home_directory, "Desktop")

        # Check if the operating system is supported and the desktop path exists
        if desktop_path and os.path.exists(desktop_path):
            return DesktopPathResponse(
                desktop_path=desktop_path, is_writable=os.access(desktop_path, os.W_OK)
            )
        else:
            raise HTTPException(status_code=404, detail="Desktop path not found")

    async def get_directory_tree(
        self, request: DirectoryRequest
    ) -> DirectoryTreeResponse:
        def _list_dir_contents(directory):
            """
            List the contents of a directory recursively, building a tree structure.

            :param directory: The path of the directory to inspect.
            :return: A nested dictionary with the contents of the directory.
            """
            tree = {
                "type": "directory",
                "name": os.path.basename(directory),
                "children": [],
            }
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
            raise HTTPException(
                status_code=400, detail="The provided path is not a directory"
            )

        # Generate the directory tree starting from the provided path
        directory_tree = _list_dir_contents(start_path)
        return DirectoryTreeResponse(directory_tree=directory_tree)

    async def get_file(self, request: FileRequest):
        try:
            return FileResponse(request.file_path)
        except FileNotFoundError:
            # If the file is not found, return a 404 error
            raise HTTPException(status_code=404, detail="File not found")

    async def upload_file(
        self, file_path: str = Form(...), file_data: UploadFile = File(...)
    ):
        try:
            file_path = os.path.expandvars(os.path.expanduser(file_path))
            with open(file_path, "wb") as f:
                content = await file_data.read()
                f.write(content)
            return BaseResponse(message="File uploaded successfully")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def get_platform(self) -> PlatformResponse:
        return PlatformResponse(
            platform=self.platform_name,
            version=platform.version(),
            machine=platform.machine(),
            architecture=platform.processor(),
        )

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
                return BaseResponse(message="File downloaded successfully")

            except requests.RequestException as e:
                error = e
                self.logger.error(
                    f"Failed to download {request.url}. Retrying... ({max_retries - i - 1} attempts left)"
                )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to download {request.url}. No retries left. Error: {error}",
        )

    async def activate_window(self, request: WindowRequest):
        if not request.window_name:
            raise HTTPException(status_code=400, detail="window_name required")

        try:
            # Attempt to activate VS Code window using wmctrl
            subprocess.run(
                [
                    "wmctrl",
                    "-{:}{:}a".format(
                        "x" if request.by_class else "", "F" if request.strict else ""
                    ),
                    request.window_name,
                ]
            )
            return BaseResponse(message="Window activated successfully")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to activate window {request.window_name}. Error: {e}",
            )

    async def close_window(self, request: WindowRequest):
        if not request.window_name:
            raise HTTPException(status_code=400, detail="window_name required")

        try:
            subprocess.run(
                [
                    "wmctrl",
                    "-{:}{:}c".format(
                        "x" if request.by_class else "", "F" if request.strict else ""
                    ),
                    request.window_name,
                ]
            )
            return BaseResponse(message="Window closed successfully")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to close window {request.window_name}. Error: {e}",
            )

    async def start_recording(self, app: FastAPI) -> RecordingResponse:
        if app.state.recording_process:
            raise HTTPException(
                status_code=400, detail="Recording is already in progress."
            )

        d = display.Display()
        screen_width = d.screen().width_in_pixels
        screen_height = d.screen().height_in_pixels

        start_command = f"ffmpeg -y -f x11grab -draw_mouse 1 -s {screen_width}x{screen_height} -i :0.0 -c:v libx264 -r 30 {app.state.recording_path}"

        app.state.recording_process = subprocess.Popen(
            shlex.split(start_command),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return RecordingResponse(
            path=app.state.recording_path,
            format="mp4",
            message="Recording started successfully",
        )

    async def end_recording(self, app: FastAPI) -> RecordingResponse:
        if not app.state.recording_process:
            raise HTTPException(
                status_code=400, detail="No recording in progress to stop."
            )

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
                message="Recording completed successfully",
            )
        else:
            raise HTTPException(status_code=404, detail="Recording failed")

    # =========== GUI interaction ===========

    # inspired by: https://github.com/e2b-dev/desktop/blob/main/packages/python-sdk/e2b_desktop/main.py

    # ================================
    # Keyboard and mouse actions space
    # ================================

    async def _wait_and_verify(
        self,
        cmd: str,
        on_result: Callable[[CommandResponse], bool],
        timeout: int = 10,
        interval: float = 0.5,
    ) -> bool:
        elapsed: float = 0
        while elapsed < timeout:
            try:
                if on_result(await self.execute_command(CommandRequest(command=cmd))):
                    return True
            except Exception as e:
                self.logger.error(f"Error executing command {cmd}: {e}")
                time.sleep(interval)
                elapsed += interval

        return False

    async def screenshot(
        self,
        format: Literal["bytes", "stream"] = "bytes",
    ):
        """
        Take a screenshot and return it in the specified format.

        :param format: The format of the screenshot. Can be 'bytes', 'blob', or 'stream'.
        :returns: The screenshot in the specified format.
        """
        if os.path.exists(self.recording_path):
            os.remove(self.recording_path)
        await self.execute_command(
            CommandRequest(command=f"scrot --pointer {self.recording_path}")
        )
        return FileResponse(self.recording_path, media_type="image/png")

    async def left_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Left click on the mouse position.
        """
        if x and y:
            await self.move_mouse(x, y)
        await self.execute_command(CommandRequest(command="xdotool click 1"))

    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Double left click on the mouse position.
        """
        if x and y:
            await self.move_mouse(x, y)
        await self.execute_command(CommandRequest(command="xdotool click --repeat 2 1"))

    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        if (x is None) != (y is None):
            raise ValueError("Both x and y must be provided together")
        """
        Right click on the mouse position.
        """
        if x and y:
            await self.move_mouse(x, y)
        await self.execute_command(CommandRequest(command="xdotool click 3"))

    async def middle_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Middle click on the mouse position.
        """
        if x and y:
            await self.move_mouse(x, y)
        await self.execute_command(CommandRequest(command="xdotool click 2"))

    async def scroll(self, direction: Literal["up", "down"] = "down", amount: int = 1):
        """
        Scroll the mouse wheel by the given amount.

        :param direction: The direction to scroll. Can be "up" or "down".
        :param amount: The amount to scroll.
        """
        await self.execute_command(
            CommandRequest(
                command=f"xdotool click --repeat {amount} {'4' if direction == 'up' else '5'}"
            )
        )

    async def move_mouse(self, x: int, y: int):
        """
        Move the mouse to the given coordinates.

        :param x: The x coordinate.
        :param y: The y coordinate.
        """
        await self.execute_command(
            CommandRequest(command=f"xdotool mousemove --sync {x} {y}")
        )

    async def mouse_press(self, button: Literal["left", "right", "middle"] = "left"):
        """
        Press the mouse button.
        """
        await self.execute_command(
            CommandRequest(command=f"xdotool mousedown {self.MOUSE_BUTTONS[button]}")
        )

    async def mouse_release(self, button: Literal["left", "right", "middle"] = "left"):
        """
        Release the mouse button.
        """
        await self.execute_command(
            CommandRequest(command=f"xdotool mouseup {self.MOUSE_BUTTONS[button]}")
        )

    async def get_cursor_position(self) -> tuple[int, int]:
        """
        Get the current cursor position.

        :return: A tuple with the x and y coordinates
        :raises RuntimeError: If the cursor position cannot be determined
        """
        result = await self.execute_command(
            CommandRequest(command="xdotool getmouselocation")
        )

        groups = re.search(r"x:(\d+)\s+y:(\d+)", result.output)
        if not groups:
            raise RuntimeError(
                f"Failed to parse cursor position from output: {result.output}"
            )

        x, y = groups.group(1), groups.group(2)
        if not x or not y:
            raise RuntimeError(f"Invalid cursor position values: x={x}, y={y}")

        return CursorPositionResponse(
            x=int(x),
            y=int(y),
            screen=0,  # TODO: Implement multi-monitor support
        )

    async def get_screen_size(self) -> tuple[int, int]:
        """
        Get the current screen size.

        :return: A tuple with the width and height
        :raises RuntimeError: If the screen size cannot be determined
        """
        result = await self.execute_command(CommandRequest(command="xrandr"))

        _match = re.search(r"(\d+x\d+)", result.output)
        if not _match:
            raise RuntimeError(
                f"Failed to parse screen size from output: {result.output}"
            )

        try:
            return ScreenSizeResponse(
                width=int(_match.group(1).split("x")[0]),
                height=int(_match.group(1).split("x")[1]),
                message="Screen size retrieved successfully",
            )
        except (ValueError, IndexError) as e:
            raise RuntimeError(f"Invalid screen size format: {_match.group(1)}") from e

    async def write(
        self, text: str, *, chunk_size: int = 25, delay_in_ms: int = 75
    ) -> None:
        """
        Write the given text at the current cursor position.

        :param text: The text to write.
        :param chunk_size: The size of each chunk of text to write.
        :param delay_in_ms: The delay between each chunk of text.
        """

        def break_into_chunks(text: str, n: int):
            for i in range(0, len(text), n):
                yield text[i : i + n]

        for chunk in break_into_chunks(text, chunk_size):
            await self.execute_command(
                CommandRequest(
                    command=f"xdotool type --delay {delay_in_ms} {shlex.quote(chunk)}"
                )
            )

    async def press(self, key: Union[str, list[str]]):
        """
        Press a key.

        :param key: The key to press (e.g. "enter", "space", "backspace", etc.).
        """
        if isinstance(key, list):
            key = "+".join(self._map_key(k) for k in key)
        else:
            key = self._map_key(key)

        await self.execute_command(CommandRequest(command=f"xdotool key {key}"))

    async def drag(self, fr: tuple[int, int], to: tuple[int, int]):
        """
        Drag the mouse from the given position to the given position.

        :param from: The starting position.
        :param to: The ending position.
        """
        await self.move_mouse(fr[0], fr[1])
        await self.mouse_press()
        await self.move_mouse(to[0], to[1])
        await self.mouse_release()

    async def wait(self, ms: int):
        """
        Wait for the given amount of time.

        :param ms: The amount of time to wait in milliseconds.
        """
        await self.execute_command(CommandRequest(command=f"sleep {ms / 1000}"))

    async def open(self, file_or_url: str):
        """
        Open a file or a URL in the default application.

        :param file_or_url: The file or URL to open.
        """
        await self.execute_command(
            CommandRequest(command=f"xdg-open {file_or_url}", background=True)
        )

    async def get_current_window_id(self) -> WindowInfoResponse:
        """
        Get the current window ID.
        """
        result = await self.execute_command(
            CommandRequest(command="xdotool getwindowfocus")
        )
        window_id = result.output.strip()
        return WindowInfoResponse(window_id=window_id)

    async def get_application_windows(self, application: str) -> WindowListResponse:
        """
        Get the window IDs of all windows for the given application.
        """
        result = await self.execute_command(
            CommandRequest(
                command=f"xdotool search --onlyvisible --class {application}"
            )
        )
        window_ids = result.output.strip().split("\n")
        return WindowListResponse(
            windows=[
                WindowInfoResponse(window_id=window_id) for window_id in window_ids
            ]
        )

    async def get_window_title(self, window_id: str) -> WindowInfoResponse:
        """
        Get the title of the window with the given ID.
        """
        result = await self.execute_command(
            CommandRequest(command=f"xdotool getwindowname {window_id}")
        )
        return WindowInfoResponse(title=result.output.strip())

    async def launch(self, application: str, uri: Optional[str] = None):
        """
        Launch an application.
        """
        await self.execute_command(
            CommandRequest(
                command=f"gtk-launch {application} {uri or ''}",
                background=True,
                timeout=0,
            )
        )
