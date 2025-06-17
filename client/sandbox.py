# isort: skip_file

import logging
import os
import time
import shlex
from typing import Any, Literal, Optional
import requests
import json
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Playwright

from .remote_provider import DockerProviderConfig, create_remote_env_provider
from .retry_decorator import retry
from dockerfiles.desktop.request_models import (
    CommandRequest,
    DirectoryRequest,
    WindowSizeRequest,
)
from dockerfiles.desktop.response_models import (
    CommandResponse,
    StatusEnum,
    PlatformResponse,
    ScreenSizeResponse,
    DesktopPathResponse,
    DirectoryTreeResponse,
    TerminalOutputResponse,
    CursorPositionResponse,
    WindowSizeResponse,
    WindowInfoResponse,
    WindowListResponse,
    RecordingResponse,
)

logger = logging.getLogger(__name__)

Params = dict[str, int | str]


class Sandbox:
    """Client for interacting with the Android environment server"""

    def __init__(
        self,
        pkgs_to_install: list[str] = [],
        os_type: Literal["Ubuntu", "Windows", "MacOS"] = "Ubuntu",
        provider_type: Literal["docker", "aws", "hf"] = "docker",
        volumes: list[str] = [],
    ):
        logger.info(
            "Setting up Android environment using Docker - Initial setup may take 5-10 minutes. Please wait..."
        )
        if os_type == "Ubuntu":
            if provider_type == "docker":
                config = DockerProviderConfig(
                    ports_to_forward={5000, 8006, 8080, 9222},
                    image="huggingface/ubuntu_xfce4:latest",
                    healthcheck_endpoint="/screenshot",
                    healthcheck_port=5000,
                    healthcheck_retry_interval=10,
                    volumes=volumes,
                    shm_size="4g",
                )
            else:
                raise NotImplementedError(
                    f"Provider type {provider_type} not implemented"
                )
        else:
            raise NotImplementedError(f"OS type {os_type} not implemented")

        self.provider = create_remote_env_provider(config=config)
        self.provider.start_emulator()
        ip_addr = self.provider.get_ip_address()
        self.base_url = f"http://{ip_addr.ip_address}:{ip_addr.host_port[5000]}"
        self.retry_times = 10
        self.retry_interval = 5
        self.pkgs_to_install = pkgs_to_install

        self.chromium_port = ip_addr.host_port[9222]
        self.browser: Optional[Browser] = None
        self.chromium_context: Optional[BrowserContext] = None
        self._playwright: Optional[Playwright] = None

    @retry(retry_times=10, retry_interval=5.0)
    def _make_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> requests.Response:
        """Make an HTTP request with retry logic"""
        url = self.base_url + endpoint
        response = requests.request(method, url, **kwargs)
        if response.status_code >= 400:
            request_info = {
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "headers": dict(response.request.headers),
                "request_kwargs": kwargs,
                "response_content": response.content.decode()
                if response.content
                else None,
                "response_headers": dict(response.headers),
            }
            raise Exception(
                f"Request failed with details:\n"
                f"Method: {request_info['method']}\n"
                f"URL: {request_info['url']}\n"
                f"Status Code: {request_info['status_code']}\n"
                f"Request Headers: {request_info['headers']}\n"
                f"Request Parameters: {request_info['request_kwargs']}\n"
                f"Response Headers: {request_info['response_headers']}\n"
                f"Response Content: {request_info['response_content']}"
            )
        return response

    # Chrome setup
    def _chrome_open_tabs_setup(self, urls_to_open: list[str]) -> None:
        host = self.provider.get_ip_address().ip_address
        port = (
            self.chromium_port
        )  # fixme: this port is hard-coded, need to be changed from config file

        remote_debugging_url = f"http://{host}:{port}"
        logger.info("Connect to Chrome @: %s", remote_debugging_url)
        logger.debug("PLAYWRIGHT ENV: %s", repr(os.environ))

        playwright = sync_playwright().start()
        for attempt in range(15):
            if attempt > 0:
                time.sleep(5)

            browser = None
            try:
                browser = playwright.chromium.connect_over_cdp(remote_debugging_url)
            except Exception as e:
                if attempt < 14:
                    logger.error(
                        f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}"
                    )
                    continue
                else:
                    logger.error(f"Failed to connect after multiple attempts: {e}")
                    playwright.stop()
                    raise e

            if not browser:
                playwright.stop()
                return None

            logger.info("Opening %s...", urls_to_open)
            for i, url in enumerate(urls_to_open):
                # Use the first context (which should be the only one if using default profile)
                if i == 0:
                    context = browser.contexts[0]
                    context.set_extra_http_headers(
                        {"Accept-Language": "en-US;q=0.7,en;q=0.6"}
                    )
                page = (
                    context.new_page()
                )  # Create a new page (tab) within the existing context
                try:
                    page.goto(url, timeout=60000)
                except Exception:
                    logger.warning(
                        "Opening %s exceeds time limit", url
                    )  # only for human test
                logger.info(f"Opened tab {i + 1}: {url}")

                if i == 0:
                    # clear the default tab
                    default_page = context.pages[0]
                    default_page.close()

            # Store playwright instance as instance variable so it can be cleaned up later
            self._playwright = playwright
            # Do not close the context or browser; they will remain open after script ends
            self.browser, self.chromium_context = browser, context

            break

    def execute_python_command(
        self, command: str, import_prefix: list[str]
    ) -> CommandResponse:
        """Executes a python command on the server."""

        for pkg in import_prefix:
            if pkg not in self.pkgs_to_install:
                # install the package
                logger.info("Installing package: %s", pkg)
                self.execute_command(f"pip install {pkg}")

        command_code = (
            "".join(f"import {pkg}; " for pkg in import_prefix) + f" {command}"
        )
        command_list = ["python", "-c", shlex.quote(command_code)]
        logger.info("Executing command: %s", " ".join(command_list))
        return self.execute_command(" ".join(command_list))

    def execute_command(
        self, command: str, background: bool = False, timeout: int = 120
    ) -> CommandResponse:
        """Executes a terminal command on the server."""
        payload = CommandRequest(
            command=command, shell=False, background=background, timeout=timeout
        )

        try:
            response = self._make_request(
                "POST",
                "/execute",
                headers={"Content-Type": "application/json"},
                data=payload.model_dump_json(),
                timeout=timeout,
            )
            return CommandResponse(**response.json())
        except Exception as e:
            logger.error("Failed to execute background command: %s", e)
            return CommandResponse(
                status=StatusEnum.ERROR,
                message=f"Failed to execute background command {command}.",
                output="",
                error=str(e),
                returncode=response.status_code,
            )

    def get_terminal_output(self) -> TerminalOutputResponse:
        """Gets the terminal output from the server."""
        response = self._make_request("GET", "/terminal")
        logger.info("Got terminal output successfully")
        return TerminalOutputResponse(**response.json())

    def get_desktop_screenshot(self) -> bytes:
        """Gets a screenshot from the server."""
        response = self._make_request("GET", "/screenshot")
        logger.info("Got screenshot successfully")
        return response.content

    def get_playwright_screenshot(self, full_page: bool = True) -> bytes | None:
        """
        Gets a screenshot using Playwright from the active browser context.
        Returns None if browser context is not available.
        """
        if self.chromium_context is None:
            logger.warning("No browser context available for screenshot")
            return None

        try:
            # Get the active page
            page = self.chromium_context.pages[0]
            # Take screenshot
            screenshot_bytes = page.screenshot(type="png", full_page=True)
            return screenshot_bytes
        except Exception as e:
            logger.error(f"Failed to take screenshot using Playwright: {e}")
            return None

    def screenshot(self) -> bytes | None:
        """
        Gets a screenshot from the server. With the cursor. None -> no screenshot or unexpected error.
        """
        return self.get_desktop_screenshot()

    def get_vm_platform(self) -> PlatformResponse:
        """
        Gets the size of the vm screen.
        """
        response = self._make_request("GET", "/platform")
        logger.info("Got platform successfully")
        return PlatformResponse(**response.json())

    def get_cursor_position(self) -> CursorPositionResponse:
        """Gets the cursor position of the vm."""
        response = self._make_request("GET", "/cursor_position")
        logger.info("Got cursor position successfully")
        return CursorPositionResponse(**response.json())

    def get_window_size(self, app_class_name: str) -> WindowSizeResponse:
        """Gets the size of the vm window."""
        payload = WindowSizeRequest(app_class_name=app_class_name)
        response = self._make_request(
            "GET",
            "/window_size",
            headers={"Content-Type": "application/json"},
            data=payload.model_dump_json(),
        )
        logger.info("Got window size successfully")
        return WindowSizeResponse(**response.json())

    def get_screen_size(self) -> ScreenSizeResponse:
        """Gets the size of the vm screen."""
        response = self._make_request("GET", "/screen_size")
        logger.info("Got screen size successfully")
        return ScreenSizeResponse(**response.json())

    def get_desktop_path(self) -> DesktopPathResponse:
        """Gets the desktop path of the vm."""
        response = self._make_request("GET", "/desktop_path")
        logger.info("Got desktop path successfully")
        return DesktopPathResponse(**response.json())

    def get_directory_tree(self, path: str) -> DirectoryTreeResponse:
        """Gets the directory tree of the vm."""
        payload = DirectoryRequest(path=path)
        response = self._make_request(
            "GET",
            "/list_directory",
            headers={"Content-Type": "application/json"},
            data=payload.model_dump_json(),
        )
        logger.info("Got directory tree successfully")
        return DirectoryTreeResponse(**response.json())

    # Record video
    def start_recording(self) -> RecordingResponse:
        """Starts recording the screen."""
        response = self._make_request("POST", "/start_recording")
        logger.info("Recording started successfully")
        return RecordingResponse(**response.json())

    def end_recording(self, dest: str) -> RecordingResponse:
        """Ends recording the screen."""
        response_end_rec = self._make_request("POST", "/end_recording")
        metadata = RecordingResponse(**response_end_rec.json())
        logger.info("Recording stopped successfully")
        response_stream = self._make_request(
            "GET", "/stream_file", params={"file_path": metadata.path}
        )
        with open(dest, "wb") as f:
            for chunk in response_stream.iter_content(chunk_size=8192):
                if not chunk:
                    break
                f.write(chunk)

        return RecordingResponse(
            path=dest,
            size=metadata.size,
            format=metadata.format,
        )

    def close(self) -> None:
        """Close the environment"""
        if self._playwright is not None:
            self._playwright.stop()
        self.provider.stop_emulator()

    def kill(self) -> None:
        """Kill the environment"""
        self.close()

    def health(self) -> bool:
        """Check the health of the environment"""
        try:
            response = requests.get(f"{self.base_url}/screenshot")
            response.raise_for_status()
        except Exception as e:
            print(f"Environment is not healthy: {e}")
            return False
        return True

    # ================================
    # Keyboard and mouse actions space
    # ================================
    def move_mouse(self, x: int, y: int):
        """
        Moves the mouse to the specified coordinates.
        """
        self._make_request("POST", "/move_mouse", params={"x": x, "y": y})

    def mouse_press(self, button: Literal["left", "right", "middle"] = "left"):
        """
        Presses the specified button of the mouse.
        """
        self._make_request("POST", "/mouse_press", params={"button": button})

    def mouse_release(self, button: Literal["left", "right", "middle"] = "left"):
        """
        Releases the specified button of the mouse.
        """
        self._make_request("POST", "/mouse_release", params={"button": button})

    def left_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Clicks the left button of the mouse at the specified coordinates.
        """
        self._make_request("POST", "/left_click", params={"x": x, "y": y})

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Clicks the right button of the mouse at the specified coordinates.
        """
        self._make_request("POST", "/right_click", params={"x": x, "y": y})

    def middle_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Clicks the middle button of the mouse at the specified coordinates.
        """
        self._make_request("POST", "/middle_click", params={"x": x, "y": y})

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        Double-clicks the left button of the mouse at the specified coordinates.
        """
        self._make_request("POST", "/double_click", params={"x": x, "y": y})

    def write(self, text: str, delay_in_ms: int = 75):
        """
        Writes the specified text at the current cursor position.
        """
        self._make_request(
            "POST",
            "/write",
            params={"text": text, "delay_in_ms": delay_in_ms},
        )

    def press(self, key: str | list[str]):
        """
        Presses a keyboard key
        """
        self._make_request(
            "POST",
            "/press",
            headers={"Content-Type": "application/json"},
            data=json.dumps(key),
        )

    def drag(self, fr: tuple[int, int], to: tuple[int, int]):
        """
        Drags the mouse from the start position to the end position.
        """
        self._make_request("POST", "/drag", params={"fr": fr, "to": to})

    def scroll(
        self, x: int, y: int, direction: Literal["up", "down"] = "down", amount: int = 1
    ):
        """
        Scrolls the mouse wheel in the specified direction.
        """
        self._make_request(
            "POST",
            "/scroll",
            params={"x": x, "y": y, "direction": direction, "amount": amount},
        )

    def wait(self, ms: int):
        """
        Waits for the specified amount of time.
        """
        time.sleep(ms / 1000)

    def open_chrome(self, url: str):
        """
        Opens the specified URL in Chrome.
        """
        logger.info("Opening Chrome")
        if self.chromium_context is None:
            self.execute_command(
                "google-chrome --remote-debugging-port=1337 --no-first-run --no-sandbox --dbus-stub --disable-gpu --disable-translate --disable-notifications --disable-infobars --user-data-dir=/home/user/.config/chrome --no-default-browser-check --disable-features=Translate",
                background=True,
            )
            time.sleep(5)
            self.execute_command(
                "socat tcp-listen:9222,fork tcp:localhost:1337", background=True
            )
            self._chrome_open_tabs_setup([url])
            time.sleep(5)
        else:
            self.chromium_context.new_page().goto(url, timeout=60000)
        if self.chromium_context is None:
            return CommandResponse(
                status=StatusEnum.ERROR,
                message="Failed to open Chrome.",
                output="",
                error="",
                returncode=1,
            )
        else:
            return CommandResponse(
                status=StatusEnum.SUCCESS, output="", error="", returncode=0
            )

    def launch(self, application: str, uri: Optional[str] = None):
        """
        Launches the specified application.
        """
        try:
            self._make_request(
                "POST",
                "/launch",
                params={"application": application, "uri": uri},
            )
            logger.info("Launched application successfully")
            return CommandResponse(
                status=StatusEnum.SUCCESS, output="", error="", returncode=0
            )
        except Exception as e:
            return CommandResponse(
                status=StatusEnum.ERROR,
                message="Failed to launch application.",
                output="",
                error=str(e),
                returncode=1,
            )

    def open(self, url_or_file: str, sleep_time: int = 10) -> CommandResponse:
        """
        Opens the specified URL or file in the default application.
        """

        if url_or_file.startswith(("http://", "https://")):
            response = self.open_chrome(url_or_file)
        else:
            try:
                response = self._make_request(
                    "POST",
                    "/open",
                    params={"url_or_file": url_or_file},
                )
                response = CommandResponse(
                    status=StatusEnum.SUCCESS, output="", error="", returncode=0
                )
                logger.info(
                    f"Waiting for the file or URL to open for {sleep_time} seconds"
                )
                time.sleep(sleep_time)
            except Exception as e:
                return CommandResponse(
                    status=StatusEnum.ERROR,
                    message="Failed to open the file or URL.",
                    output="",
                    error=str(e),
                    returncode=1,
                )

        if response.status == StatusEnum.ERROR:
            return response

        # Try to maximize the window using the window title
        logger.info("Maximizing the window")
        response = self.execute_command(
            "wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz"
        )
        time.sleep(3)
        return response

    def get_current_window_id(self) -> WindowInfoResponse:
        response = self._make_request("GET", "/get_current_window_id")
        logger.info("Got current window ID successfully")
        return WindowInfoResponse(**response.json())

    def get_window_title(self, window_id: str) -> WindowInfoResponse:
        response = self._make_request(
            "GET", "/get_window_title", params={"window_id": window_id}
        )
        logger.info("Got window title successfully")
        return WindowInfoResponse(**response.json())

    def get_application_windows(self, application: str) -> WindowListResponse:
        response = self._make_request(
            "GET",
            "/get_application_windows",
            params={"application": application},
        )
        logger.info("Got application windows successfully")
        return WindowListResponse(**response.json())

    # ================================


if __name__ == "__main__":
    client = Sandbox()
    # obs = client.get_obs(require_terminal=True)

    def save_desktop_screenshot():
        screenshot = client.get_desktop_screenshot()
        if screenshot:
            with open("screenshot_desktop.png", "wb") as f:
                f.write(screenshot)

    def save_playwright_screenshot():
        screenshot = client.get_playwright_screenshot()
        if screenshot:
            with open("screenshot_playwright.png", "wb") as f:
                f.write(screenshot)

    def shell():
        while True:
            inp = input(">$ ")
            result = client.execute_command(inp)
            if result.status == StatusEnum.ERROR:
                print(result.message)
            else:
                if result.output:
                    print(result.output)
                else:
                    print(result.error)
            save_desktop_screenshot()
            save_playwright_screenshot()

    def open_url():
        logger.info("Opening URL")
        client.open("https://www.rentalcars.com/")
        logger.info("Saving screenshot")
        # save_screenshot()
        save_desktop_screenshot()

    def test_actions():
        actions = [
            ("Move mouse to (100, 100)", lambda: client.move_mouse(100, 100)),
            ("Left click", lambda: client.left_click()),
            ("Right click", lambda: client.right_click()),
            ("Move mouse to (500, 500)", lambda: client.move_mouse(500, 400)),
            ("Double click", lambda: client.double_click()),
            ("Write 'Hello, world!'", lambda: client.write("Hello, world!")),
            ("Press Enter", lambda: client.press(["Ctrl", "C"])),
            ("Press Enter", lambda: client.press("Enter")),
            ("Open rentalcars.com", lambda: client.open("https://www.rentalcars.com/")),
            ("Scroll at (100, 100)", lambda: client.scroll(100, 100)),
            ("Execute 'ls -l'", lambda: client.execute_command("ls -l")),
            (
                "Execute Python print",
                lambda: client.execute_command("print('Hello, world!')"),
            ),
        ]

        for action_name, action_func in actions:
            logger.info(f"\nNext action: {action_name}")
            action_func()
            input("Press Enter to execute this action...")
            save_desktop_screenshot()
            logger.info("Saved screenshot")
            input("Press Enter to continue to next action...")

    try:
        open_url()
        test_actions()
        # shell()
    except (KeyboardInterrupt, EOFError):
        logger.info("Exiting...")
    except Exception as e:
        print(e)

    client.close()
