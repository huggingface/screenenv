# isort: skip_file

import logging
import os
import time
import shlex
from typing import Any, Callable, Literal, Optional
import uuid
import subprocess

import requests
import webbrowser
import json
from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Playwright,
)
from urllib.parse import urlparse

from .remote_provider import DockerProviderConfig, create_remote_env_provider
from .retry_decorator import retry
from dockerfiles.desktop.request_models import (
    CommandRequest,
    DirectoryRequest,
    FileRequest,
    DownloadRequest,
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
    AccessibilityTreeResponse,
)

logger = logging.getLogger(__name__)

Params = dict[str, int | str]

# Screen size options for desktop environments
ScreenSize = Literal[
    # Standard Desktop Resolutions
    "1920x1080",  # Full HD (most common)
    "1366x768",  # HD (laptop standard)
    "2560x1440",  # 2K/QHD
    "3840x2160",  # 4K/UHD
    "1280x720",  # HD Ready
    "1600x900",  # HD+
    "1920x1200",  # WUXGA
    "2560x1600",  # WQXGA
    "3440x1440",  # Ultrawide QHD
    "5120x1440",  # Super Ultrawide
    "1920x600",  # Custom wide (current default)
    # Mobile/Tablet Resolutions
    "1024x768",  # iPad (portrait)
    "768x1024",  # iPad (landscape)
    "360x640",  # Mobile portrait
    "640x360",  # Mobile landscape
    # Legacy Resolutions
    "1024x600",  # Netbook
    "800x600",  # SVGA
    "640x480",  # VGA
    # Additional Common Resolutions
    "1440x900",  # Custom laptop
    "1680x1050",  # WSXGA+
    "1920x1440",  # Custom 4:3 ratio
    "2560x1080",  # Ultrawide Full HD
    "3440x1440",  # Ultrawide QHD
    "3840x1080",  # Super Ultrawide Full HD
]


class Sandbox:
    """Client for interacting with the Android environment server"""

    def __init__(
        self,
        os_type: Literal["Ubuntu", "Windows", "MacOS"] = "Ubuntu",
        provider_type: Literal["docker", "aws", "hf"] = "docker",
        volumes: list[str] = [],
        headless: bool = True,
        auto_ssl: bool = False,
        screen_size: ScreenSize = "1920x1080",
    ):
        logger.info(
            "Setting up Android environment using Docker - Initial setup may take 5-10 minutes. Please wait..."
        )
        self.session_password = uuid.uuid4().hex
        self.auto_ssl = auto_ssl
        self.ssl_cert_file: Optional[str] = None
        self.environment = {
            "DISK_SIZE": "32G",
            "RAM_SIZE": "4G",
            "CPU_CORES": "4",
            "SESSION_PASSWORD": self.session_password,
            "SCREEN_SIZE": f"{screen_size}x24",
        }

        self.volumes = volumes
        if self.auto_ssl:
            try:
                self.ssl_cert_file = self._generate_ssl_certificate()
                # Read the certificate content and pass it as environment variable
                with open(self.ssl_cert_file, "r") as f:
                    cert_content = f.read()
                self.environment["SSL_ENABLED"] = "true"
                self.environment["SSL_CERT_CONTENT"] = cert_content
                # Keep the certificate file for browser use
                logger.info(f"SSL certificate generated at: {self.ssl_cert_file}")
            except Exception as e:
                logger.warning(
                    f"Failed to generate SSL certificate, falling back to non-SSL mode: {e}"
                )
                self.auto_ssl = False
                if self.ssl_cert_file and os.path.exists(self.ssl_cert_file):
                    os.unlink(self.ssl_cert_file)
                self.ssl_cert_file = None

        if os_type == "Ubuntu":
            if provider_type == "docker":
                config = DockerProviderConfig(
                    ports_to_forward={5000, 8006, 9222},
                    image="huggingface/ubuntu_xfce4:latest",
                    healthcheck_endpoint="/screenshot",
                    healthcheck_port=5000,
                    healthcheck_retry_interval=10,
                    healthcheck_headers={"X-Session-Password": self.session_password},
                    volumes=volumes,
                    shm_size="4g",
                    environment=self.environment,
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
        self.pkgs_to_install: list[str] = []

        self.chromium_port = ip_addr.host_port[9222]
        self.browser: Optional[Browser] = None
        self.chromium_context: Optional[BrowserContext] = None
        self._playwright: Optional[Playwright] = None
        self.headless = headless
        if not headless:
            self.vnc_port = ip_addr.host_port[8006]
            # Use HTTPS when SSL is enabled (certificate is handled by noVNC in container)
            vnc_protocol = "https" if self.auto_ssl else "http"
            # Connect to the container's exposed port from the host
            self.vnc_url = f"{vnc_protocol}://{ip_addr.ip_address}:{self.vnc_port}/vnc.html?host={ip_addr.ip_address}&port={self.vnc_port}&autoconnect=true&password={self.session_password}"
            logger.info(
                f"Opening VNC connection with {'SSL enabled' if self.auto_ssl else 'SSL disabled'}"
            )

            webbrowser.open(self.vnc_url)

    def _generate_ssl_certificate(self) -> str:
        """Generate a temporary SSL certificate for VNC"""
        # Create certificate in a location that Docker can access
        cert_dir = os.path.expanduser("~/screenenv_certs")
        os.makedirs(cert_dir, exist_ok=True)

        cert_file = os.path.join(cert_dir, f"cert_{uuid.uuid4().hex}.pem")

        try:
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:4096",
                    "-keyout",
                    cert_file,
                    "-out",
                    cert_file,
                    "-days",
                    "365",
                    "-nodes",
                    "-subj",
                    "/C=US/ST=State/L=City/O=Organization/CN=*",
                ],
                check=True,
            )
            logger.info("Generated SSL certificate: %s", cert_file)
            return cert_file
        except subprocess.CalledProcessError:
            if os.path.exists(cert_file):
                os.unlink(cert_file)
            raise RuntimeError("Failed to generate SSL certificate")

    @retry(retry_times=10, retry_interval=5.0)
    def _make_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> requests.Response:
        """Make an HTTP request with retry logic"""
        url = self.base_url + endpoint

        # Ensure headers exist in kwargs
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add session password header
        kwargs["headers"]["X-Session-Password"] = self.session_password

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
        port = self.chromium_port

        remote_debugging_url = f"http://{host}:{port}"
        logger.info("Connect to Chrome @: %s", remote_debugging_url)
        logger.debug("PLAYWRIGHT ENV: %s", repr(os.environ))

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        for attempt in range(15):
            if attempt > 0:
                time.sleep(5)

            browser = None
            try:
                browser = self._playwright.chromium.connect_over_cdp(
                    remote_debugging_url
                )
            except Exception as e:
                if attempt < 14:
                    logger.error(
                        f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}"
                    )
                    continue
                else:
                    logger.error(f"Failed to connect after multiple attempts: {e}")
                    self._playwright.stop()
                    raise e

            if not browser:
                self._playwright.stop()
                self._playwright = None
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

            # Do not close the context or browser; they will remain open after script ends
            self.browser, self.chromium_context = browser, context

            break

    def health(self) -> bool:
        """Check the health of the environment"""
        try:
            response = self._make_request("GET", "/screenshot")
            response.raise_for_status()
        except Exception as e:
            print(f"Environment is not healthy: {e}")
            return False
        return True

    def _wait_and_verify(
        self,
        cmd: str,
        on_result: Callable[[CommandResponse], bool],
        timeout: int = 10,
        interval: float = 0.5,
    ) -> bool:
        elapsed: float = 0
        while elapsed < timeout:
            try:
                if on_result(self.execute_command(command=cmd)):
                    return True
            except Exception as e:
                logger.error(f"Error executing command {cmd}: {e}")
                time.sleep(interval)
                elapsed += interval

        return False

    def execute_python_command(
        self, command: str, import_prefix: list[str]
    ) -> CommandResponse:
        """Executes a python command on the server."""

        pkgs_installed = self.pkgs_to_install.copy()
        for pkg in import_prefix:
            if pkg not in pkgs_installed:
                # install the package
                logger.info("Installing package: %s", pkg)
                self.execute_command(f"pip install {pkg}")
                self.pkgs_to_install.append(pkg)

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
            command=command, background=background, timeout=timeout
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

    def get_accessibility_tree(self) -> AccessibilityTreeResponse:
        """Gets the accessibility tree of the vm."""
        response = self._make_request("GET", "/accessibility")
        logger.info("Got accessibility tree successfully")
        return AccessibilityTreeResponse(**response.json())

    def desktop_path(self) -> DesktopPathResponse:
        """Gets the desktop path of the vm."""
        response = self._make_request("GET", "/desktop_path")
        logger.info("Got desktop path successfully")
        return DesktopPathResponse(**response.json())

    def directory_tree(self, path: str) -> DirectoryTreeResponse:
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

    def download_file_from_remote(self, remote_path: str, local_dest: str) -> None:
        """Gets the file from the vm."""
        file_request = FileRequest(file_path=remote_path)
        response_stream = self._make_request(
            "GET",
            "/file",
            headers={"Content-Type": "application/json"},
            data=file_request.model_dump_json(),
        )
        with open(local_dest, "wb") as f:
            for chunk in response_stream.iter_content(chunk_size=8192):
                if not chunk:
                    break
                f.write(chunk)
        logger.info(
            f"Downloaded file from remote '{remote_path}' to local '{local_dest}'"
        )

    def upload_file_to_remote(self, local_path: str, remote_path: str = ".") -> None:
        """
        Uploads a file from the local machine to the remote environment at the specified remote path.
        """
        with open(local_path, "rb") as f:
            files = {
                "file_data": (os.path.basename(local_path), f),
            }
            data = {"file_path": remote_path}
            self._make_request(
                "POST",
                "/upload",
                files=files,
                data=data,
            )
        logger.info(f"Uploaded local file '{local_path}' to remote '{remote_path}'")

    def download_url_file_to_remote(self, url: str, remote_path: str) -> None:
        """
        Instructs the remote environment to download a file from a URL to a specified path inside the remote environment.
        """
        payload = DownloadRequest(url=url, path=remote_path)
        self._make_request(
            "POST",
            "/download_url",
            headers={"Content-Type": "application/json"},
            data=payload.model_dump_json(),
        )
        logger.info(f"Remote environment downloaded URL '{url}' to '{remote_path}'")

    def desktop_screenshot(self) -> bytes:
        """Gets a screenshot from the server."""
        response = self._make_request("GET", "/screenshot")
        logger.info("Got screenshot successfully")
        return response.content

    def playwright_screenshot(self, full_page: bool = True) -> bytes | None:
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
            screenshot_bytes = page.screenshot(type="png", full_page=full_page)
            return screenshot_bytes
        except Exception as e:
            logger.error(f"Failed to take screenshot using Playwright: {e}")
            return None

    def platform(self) -> PlatformResponse:
        """
        Gets the size of the vm screen.
        """
        response = self._make_request("GET", "/platform")
        logger.info("Got platform successfully")
        return PlatformResponse(**response.json())

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
        file_request = FileRequest(file_path=metadata.path)
        response_stream = self._make_request(
            "GET",
            "/file",
            headers={"Content-Type": "application/json"},
            data=file_request.model_dump_json(),
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

    def wait(self, ms: int):
        """
        Waits for the specified amount of time.
        """
        self._make_request("POST", "/wait", params={"ms": ms})

    def open(self, file_or_url: str) -> CommandResponse:
        """
        Opens the specified URL or file in the default application.
        """
        self._make_request(
            "POST",
            "/open",
            params={"file_or_url": file_or_url},
        )
        url_parsed = urlparse(file_or_url)
        if url_parsed.scheme and url_parsed.netloc:
            self._chrome_open_tabs_setup([file_or_url])
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

    def get_current_window_id(self) -> str:
        response = self._make_request("GET", "/current_window_id")
        logger.info("Got current window ID successfully")
        window_info_response = WindowInfoResponse(**response.json())
        return window_info_response.window_id or ""

    def get_application_windows(self, application: str) -> list[str]:
        response = self._make_request(
            "GET",
            "/application_windows",
            params={"application": application},
        )
        logger.info("Got application windows successfully")
        window_list_response = WindowListResponse(**response.json())
        return [
            win.window_id
            for win in window_list_response.windows
            if win.window_id is not None
        ]

    def get_window_title(self, window_id: str) -> str:
        response = self._make_request(
            "GET", "/window_name", params={"window_id": window_id}
        )
        logger.info("Got window title successfully")
        window_info_response = WindowInfoResponse(**response.json())
        return window_info_response.window_name or ""

    def window_size(self, window_id: str) -> WindowSizeResponse:
        """Gets the size of the vm window."""
        response = self._make_request(
            "GET", "/window_size", params={"window_id": window_id}
        )
        logger.info("Got window size successfully")
        return WindowSizeResponse(**response.json())

    def activate_window(self, window_id: str):
        response = self._make_request(
            "POST",
            "/activate_window",
            params={"window_id": window_id},
        )
        logger.info("Activated window successfully")
        return WindowInfoResponse(**response.json())

    def close_window(self, window_id: str):
        response = self._make_request(
            "POST",
            "/close_window",
            params={"window_id": window_id},
        )
        logger.info("Closed window successfully")
        return WindowInfoResponse(**response.json())

    def get_terminal_output(self) -> TerminalOutputResponse:
        response = self._make_request("GET", "/terminal")
        logger.info("Got terminal output successfully")
        return TerminalOutputResponse(**response.json())

    # ================================
    # Keyboard and mouse actions space
    # ================================

    def screenshot(self) -> bytes | None:
        """
        Gets a screenshot from the server. With the cursor. None -> no screenshot or unexpected error.
        """
        return self.desktop_screenshot()

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

    def get_cursor_position(self) -> tuple[int, int]:
        """Gets the cursor position of the vm."""
        try:
            response = self._make_request("GET", "/cursor_position")
            logger.info("Got cursor position successfully")
            cursor_position_response = CursorPositionResponse(**response.json())
            return (
                cursor_position_response.x,
                cursor_position_response.y,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get cursor position: {e}") from e

    def get_screen_size(self) -> tuple[int, int]:
        """Gets the size of the vm screen."""
        try:
            response = self._make_request("GET", "/screen_size")
            logger.info("Got screen size successfully")
            screen_size_response = ScreenSizeResponse(**response.json())
            return (
                screen_size_response.width,
                screen_size_response.height,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get screen size: {e}") from e

    def write(self, text: str, *, delay_in_ms: int = 75) -> None:
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
        self._make_request(
            "POST",
            "/drag",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fr": fr, "to": to}),
        )

    def close(self) -> None:
        """Close the environment"""
        if self._playwright is not None:
            self._playwright.stop()

        # Clean up SSL certificate if it exists
        if (
            hasattr(self, "ssl_cert_file")
            and self.ssl_cert_file
            and os.path.exists(self.ssl_cert_file)
        ):
            try:
                os.unlink(self.ssl_cert_file)
                logger.info(f"Cleaned up SSL certificate: {self.ssl_cert_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up SSL certificate: {e}")

        self.provider.stop_emulator()

    def kill(self) -> None:
        """Kill the environment"""
        self.close()


if __name__ == "__main__":
    client = Sandbox()
    # obs = client.get_obs(require_terminal=True)

    def save_desktop_screenshot():
        screenshot = client.desktop_screenshot()
        if screenshot:
            with open("screenshot_desktop.png", "wb") as f:
                f.write(screenshot)

    def save_playwright_screenshot():
        screenshot = client.playwright_screenshot()
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
