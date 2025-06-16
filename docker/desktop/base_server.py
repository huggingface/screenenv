# inspired by: https://github.com/xlang-ai/OSWorld/blob/main/desktop_env/server/main.py

import logging
import platform
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Callable, Literal, Optional, Union

import pyautogui
from fastapi import FastAPI, File, Form, UploadFile

from .request_models import (
    CommandRequest,
    DirectoryRequest,
    DownloadRequest,
    FileRequest,
    WindowRequest,
    WindowSizeRequest,
)
from .response_models import (
    CommandResponse,
    CursorPositionResponse,
    DesktopPathResponse,
    DirectoryTreeResponse,
    PlatformResponse,
    RecordingResponse,
    ScreenSizeResponse,
    WindowInfoResponse,
    WindowListResponse,
    WindowSizeResponse,
)

pyautogui.PAUSE = 0
pyautogui.DARWIN_CATCH_UP_TIME = 0

BaseWrapper = Any


class BaseServer(ABC):
    def __init__(self):
        self.platform_name = platform.system()
        self.recording_process: Optional[subprocess.Popen] = None
        self.app = FastAPI(lifespan=self.lifespan)
        self.logger = logging.getLogger("uvicorn.access")
        # Register all routes
        self._register_routes()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(handler)

        yield

        if self.recording_process:
            self.recording_process.send_signal(signal.SIGINT)
            self.recording_process.wait()

    def _register_routes(self):
        # Setup routes
        self.app.post("/execute")(self.execute_command)
        self.app.get("/terminal")(self.get_terminal_output)
        self.app.get("/accessibility")(self.get_accessibility_tree)
        self.app.post("/desktop_path")(self.get_desktop_path)
        self.app.post("/list_directory")(self.get_directory_tree)
        self.app.post("/file")(self.get_file)
        self.app.post("/setup/upload")(self.upload_file)
        self.app.get("/platform")(self.get_platform)
        self.app.post("/setup/download_file")(self.download_file)
        self.app.post("/setup/activate_window")(self.activate_window)
        self.app.post("/setup/close_window")(self.close_window)
        self.app.post("/start_recording")(self.start_recording)
        self.app.post("/end_recording")(self.end_recording)
        # GUI operations
        self.app.get("/screenshot")(self.screenshot)
        self.app.post("/left_click")(self.left_click)
        self.app.post("/double_click")(self.double_click)
        self.app.post("/right_click")(self.right_click)
        self.app.post("/middle_click")(self.middle_click)
        self.app.post("/scroll")(self.scroll)
        self.app.post("/move_mouse")(self.move_mouse)
        self.app.post("/mouse_press")(self.mouse_press)
        self.app.post("/mouse_release")(self.mouse_release)
        self.app.get("/cursor_position")(self.get_cursor_position)
        self.app.post("/screen_size")(self.get_screen_size)
        self.app.post("/window_size")(self.get_window_size)
        self.app.post("/write")(self.write)
        self.app.post("/press")(self.press)
        self.app.post("/drag")(self.drag)
        self.app.post("/wait")(self.wait)
        self.app.post("/open")(self.open)
        self.app.post("/get_current_window_id")(self.get_current_window_id)
        self.app.post("/get_application_windows")(self.get_application_windows)
        self.app.post("/get_window_title")(self.get_window_title)
        self.app.post("/launch")(self.launch)

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

    async def get_platform(self) -> PlatformResponse:
        return PlatformResponse(
            platform=self.platform_name,
            version=platform.version(),
            machine=platform.machine(),
            architecture=platform.processor(),
        )

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

    @abstractmethod
    async def execute_command(
        self, request: CommandRequest, retry_times: int = 3
    ) -> CommandResponse: ...

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

    @abstractmethod
    async def get_terminal_output(self): ...

    @abstractmethod
    async def get_accessibility_tree(self): ...

    @abstractmethod
    async def get_window_size(
        self, request: WindowSizeRequest
    ) -> WindowSizeResponse | None: ...

    @abstractmethod
    async def get_desktop_path(self) -> DesktopPathResponse: ...

    @abstractmethod
    async def get_directory_tree(
        self, request: DirectoryRequest
    ) -> DirectoryTreeResponse: ...

    @abstractmethod
    async def get_file(self, request: FileRequest): ...

    @abstractmethod
    async def upload_file(
        self, file_path: str = Form(...), file_data: UploadFile = File(...)
    ): ...

    @abstractmethod
    async def download_file(self, request: DownloadRequest): ...

    @abstractmethod
    async def activate_window(self, request: WindowRequest): ...

    @abstractmethod
    async def close_window(self, request: WindowRequest): ...

    @abstractmethod
    async def start_recording(self, app: FastAPI) -> RecordingResponse: ...

    @abstractmethod
    async def end_recording(self, app: FastAPI) -> RecordingResponse: ...

    # =========== GUI interaction ===========

    # inspired by: https://github.com/e2b-dev/desktop/blob/main/packages/python-sdk/e2b_desktop/main.py

    # ================================
    # Keyboard and mouse actions space
    # ================================

    @abstractmethod
    async def screenshot(
        self,
        format: Literal["bytes", "stream"] = "bytes",
    ): ...

    @abstractmethod
    async def left_click(self, x: Optional[int] = None, y: Optional[int] = None): ...

    @abstractmethod
    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None): ...

    @abstractmethod
    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None): ...

    @abstractmethod
    async def middle_click(self, x: Optional[int] = None, y: Optional[int] = None): ...

    @abstractmethod
    async def scroll(
        self, direction: Literal["up", "down"] = "down", amount: int = 1
    ): ...

    @abstractmethod
    async def move_mouse(self, x: int, y: int): ...

    @abstractmethod
    async def mouse_press(
        self, button: Literal["left", "right", "middle"] = "left"
    ): ...

    @abstractmethod
    async def mouse_release(
        self, button: Literal["left", "right", "middle"] = "left"
    ): ...

    @abstractmethod
    async def get_cursor_position(self) -> CursorPositionResponse: ...

    @abstractmethod
    async def get_screen_size(self) -> ScreenSizeResponse: ...

    @abstractmethod
    async def write(
        self, text: str, *, chunk_size: int = 25, delay_in_ms: int = 75
    ) -> None: ...

    @abstractmethod
    async def press(self, key: Union[str, list[str]]): ...

    @abstractmethod
    async def drag(self, fr: tuple[int, int], to: tuple[int, int]): ...

    @abstractmethod
    async def wait(self, ms: int): ...

    @abstractmethod
    async def open(self, file_or_url: str): ...

    @abstractmethod
    async def get_current_window_id(self) -> WindowInfoResponse: ...

    @abstractmethod
    async def get_application_windows(self, application: str) -> WindowListResponse: ...

    @abstractmethod
    async def get_window_title(self, window_id: str) -> WindowInfoResponse: ...

    @abstractmethod
    async def launch(self, application: str, uri: Optional[str] = None): ...
