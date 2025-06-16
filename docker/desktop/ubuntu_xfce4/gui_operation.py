

# =========== GUI interaction ===========

# inspired by: https://github.com/e2b-dev/desktop/blob/main/packages/python-sdk/e2b_desktop/main.py


MOUSE_BUTTONS = {
    "left": 1,
    "right": 3,
    "middle": 2
}

KEYS = {
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
    "windows": "Super_L"
}

def map_key(key: str) -> str:
    lower_key = key.lower()
    if lower_key in KEYS:
        return KEYS[lower_key]
    return lower_key

class DesktopEnvClient:
    """Client for interacting with the Android environment server"""

    def __init__(
        self,
        pkgs_prefix: str = "import pyautogui; import time; pyautogui.FAILSAFE = False; {command}",
        apt_packages: list[str] = ["xdotool", "xclip", "scrot", "firefox-esr"],
        path_to_vm: None | str = None,
        os_type: Literal["Ubuntu", "Windows"] = "Ubuntu",
    ):
        if path_to_vm is None:
            path_to_vm = get_osworld_vm_path(os_type)
        volumes = [f"{os.path.abspath(path_to_vm)}:/System.qcow2:ro"]
        logger.info("Setting up Android environment using Docker - Initial setup may take 5-10 minutes. Please wait...")
        self.provider = create_remote_env_provider(
            config=DockerProviderConfig(
                ports_to_forward={5000, 8006, 8080, 9222},
                image="happysixd/osworld-docker:latest",
                healthcheck_endpoint="/screenshot",
                healthcheck_port=5000,
                privileged=True,
                cap_add=["NET_ADMIN"],
                devices=["/dev/kvm"],
                volumes=volumes,
                user="root",
            )
        )
        self.provider.start_emulator()
        ip_addr = self.provider.get_ip_address()
        self.base_url = f"http://{ip_addr.ip_address}:{ip_addr.host_port[5000]}"
        self.retry_times = 10
        self.retry_interval = 5
        self.pkgs_prefix = pkgs_prefix
        self.apt_packages = apt_packages
        # self.install_apt_packages(self.apt_packages)

        self.chromium_port = ip_addr.host_port[9222]
        self.browser: Browser | None = None
        self.chromium_context: BrowserContext | None = None
        self._playwright: Playwright | None = None

    def install_apt_packages(self, apt_packages: list[str]):
        """
        Installs the apt packages on the server.
        """
        cmds = [
            "apt-get update",
            f"apt-get install -y {' '.join(apt_packages)}",
        ]
        for cmd in cmds:
            logger.info(f"Running command: {cmd}")
            self.execute_shell_command(cmd)

    # Chrome setup
    def _chrome_open_tabs_setup(self, urls_to_open: list[str]) -> None:
        host = self.provider.get_ip_address().ip_address
        port = self.chromium_port  # fixme: this port is hard-coded, need to be changed from config file

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
                    logger.error(f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}")
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
                    context.set_extra_http_headers({"Accept-Language": "en-US;q=0.7,en;q=0.6"})
                page = context.new_page()  # Create a new page (tab) within the existing context
                try:
                    page.goto(url, timeout=60000)
                except Exception as e:
                    logger.warning("Opening %s exceeds time limit", url)  # only for human test
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

    # ================================
    # Keyboard and mouse actions space
    # ================================
    def move_mouse(self, x: int, y: int) -> ExecuteResult:
        """
        Moves the mouse to the specified coordinates.
        """
        return self.execute_python_command(f"pyautogui.moveTo({x}, {y})")

    def left_click(self) -> ExecuteResult:
        """
        Clicks the left button of the mouse at the specified coordinates.
        """
        return self.execute_python_command("pyautogui.click(button='left')")

    def right_click(self) -> ExecuteResult:
        """
        Clicks the right button of the mouse at the specified coordinates.
        """
        return self.execute_python_command("pyautogui.click(button='right')")

    def double_click(self) -> ExecuteResult:
        """
        Double-clicks the left button of the mouse at the specified coordinates.
        """
        return self.execute_python_command("pyautogui.doubleClick(button='left')")

    def write(self, text: str | list[str], delay_in_ms: int = 75) -> ExecuteResult:
        """
        Writes the specified text at the current cursor position.
        """
        return self.execute_python_command(f"pyautogui.write('{text}', interval={delay_in_ms / 1000})")

    def press(self, key: str | list[str]) -> ExecuteResult:
        """
        Presses a keyboard key
        """
        if isinstance(key, str):
            return self.execute_python_command(f"pyautogui.press('{key}')")
        else:
            return self.execute_python_command(f"pyautogui.hotkey({', '.join([f'{key}' for key in key])})")

    def drag(self, start: tuple[int, int], end: tuple[int, int]) -> ExecuteResult:
        """
        Drags the mouse from the start position to the end position.
        """
        self.move_mouse(start[0], start[1])
        return self.execute_python_command(
            f"pyautogui.dragTo({end[0]}, {end[1]}, duration=1.0, button='left', mouseDownUp=True)"
        )

    def scroll(self, x: int, y: int, direction: Literal["up", "down"] = "down", amount: int = 2) -> ExecuteResult:
        """
        Scrolls the mouse wheel in the specified direction.
        """
        if direction == "down":
            amount = -amount
        return self.execute_python_command(f"pyautogui.scroll({amount}, x={x}, y={y})")

    def open_chrome(self, url: str) -> ExecuteResult:
        """
        Opens the specified URL in Chrome.
        """
        logger.info("Opening Chrome")
        if self.chromium_context is None:
            self.execute_shell_command(
                "google-chrome --remote-debugging-port=1337 --disable-features=Translate",
                background=True,
            )
            time.sleep(5)
            self.execute_shell_command("socat tcp-listen:9222,fork tcp:localhost:1337", background=True)
            self._chrome_open_tabs_setup([url])
            time.sleep(5)
        else:
            self.chromium_context.new_page().goto(url, timeout=60000)
        if self.chromium_context is None:
            return ExecuteError(status="error", message="Failed to open Chrome.")
        else:
            return ExecuteResponse(status="success", output="", error="", returncode=0)

    def open(self, url_or_file: str, sleep_time: int = 10) -> ExecuteResult:
        """
        Opens the specified URL or file in the default application.
        """

        if url_or_file.startswith(("http://", "https://")):
            response = self.open_chrome(url_or_file)
        else:
            response = self.execute_shell_command(f"xdg-open {url_or_file}", background=True)
            logger.info(f"Waiting for the application to open for {sleep_time} seconds")
            time.sleep(sleep_time)

        if isinstance(response, ExecuteError):
            return response

        # Try to maximize the window using the window title
        logger.info("Maximizing the window")
        response = self.execute_shell_command("wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz")
        time.sleep(3)
        return response

    # ================================

    def execute_python_command(self, command: str) -> ExecuteResult:
        """
        Executes a python command on the server.
        It can be used to execute the pyautogui commands, or... any other python command. who knows?
        """
        # command_list = ["python", "-c", self.pkgs_prefix.format(command=command)]
        command_list = ["python", "-c", self.pkgs_prefix.format(command=command)]
        payload = json.dumps({"command": command_list, "shell": False})

        for _ in range(self.retry_times):
            try:
                response = requests.post(
                    self.base_url + "/execute",
                    headers={"Content-Type": "application/json"},
                    data=payload,
                    timeout=90,
                )
                if response.status_code == 200:
                    logger.info("Command executed successfully: %s", response.text)
                    result = response.json()
                    if result["status"] == "error":
                        return ExecuteError(status="error", message=result["message"])
                    else:
                        return ExecuteResponse(**result)
                else:
                    logger.error("Failed to execute command. Status code: %d", response.status_code)
                    logger.info("Retrying to execute command.")
            except requests.exceptions.ReadTimeout:
                break
            except Exception as e:
                logger.error("An error occurred while trying to execute the command: %s", e)
                logger.info("Retrying to execute command.")
            time.sleep(self.retry_interval)

        logger.error("Failed to execute command.")
        return ExecuteError(status="error", message=f"Failed to execute command {command}.")

    def execute_shell_command(self, command: str, background: bool = False, timeout: int = 120) -> ExecuteResult:
        """
        Executes a terminal command on the server.
        If the command ends with &, it will be executed in the background and return immediately.
        """
        command_list = [command]
        payload = json.dumps({"command": command_list, "shell": True})

        if command.strip().endswith("&"):
            command = command.strip()[:-1]
            background = True

        # If command ends with &, execute it in background
        if background:
            try:
                requests.post(
                    self.base_url + "/setup/launch",
                    headers={"Content-Type": "application/json"},
                    data=payload,
                    timeout=5,
                )
                return ExecuteResponse(status="success", output="", error="", returncode=0)
            except Exception as e:
                logger.error("An error occurred while trying to execute the background command: %s", e)
                return ExecuteError(status="error", message=f"Failed to execute background command {command}.")

        # For non-background commands, use the existing retry logic
        for _ in range(self.retry_times):
            try:
                response = requests.post(
                    self.base_url + "/execute",
                    headers={"Content-Type": "application/json"},
                    data=payload,
                    timeout=timeout,
                )
                if response.status_code == 200:
                    logger.info("Command executed successfully: %s", response.text)
                    result = response.json()
                    if result["status"] == "error":
                        return ExecuteError(status="error", message=result["message"])
                    else:
                        return ExecuteResponse(**result)
                else:
                    logger.error("Failed to execute command. Status code: %d", response.status_code)
                    logger.info("Retrying to execute command.")
            except requests.exceptions.ReadTimeout:
                break
            except Exception as e:
                logger.error("An error occurred while trying to execute the command: %s", e)
                logger.info("Retrying to execute command.")
            time.sleep(self.retry_interval)

        logger.error("Failed to execute command.")
        return ExecuteError(status="error", message=f"Failed to execute command {command}.")

    def get_terminal_output(self) -> str | None:
        """
        Gets the terminal output from the server. None -> no terminal output or unexpected error.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.get(self.base_url + "/terminal")
                if response.status_code == 200:
                    logger.info("Got terminal output successfully")
                    return response.json()["output"]
                else:
                    logger.error("Failed to get terminal output. Status code: %d", response.status_code)
                    logger.info("Retrying to get terminal output.")
            except Exception as e:
                logger.error("An error occurred while trying to get the terminal output: %s", e)
                logger.info("Retrying to get terminal output.")
            time.sleep(self.retry_interval)

        logger.error("Failed to get terminal output.")
        return None

    def get_desktop_screenshot(self) -> bytes | None:
        """
        Gets a screenshot from the server. With the cursor. None -> no screenshot or unexpected error.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.get(self.base_url + "/screenshot")
                if response.status_code == 200:
                    logger.info("Got screenshot successfully")
                    return response.content
                else:
                    logger.error("Failed to get screenshot. Status code: %d", response.status_code)
                    logger.info("Retrying to get screenshot.")
            except Exception as e:
                logger.error("An error occurred while trying to get the screenshot: %s", e)
                logger.info("Retrying to get screenshot.")
            time.sleep(self.retry_interval)

        logger.error("Failed to get screenshot.")
        return None

    def get_playwright_screenshot(self) -> bytes | None:
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

    def get_obs(self, require_terminal: bool = False):
        # We provide screenshot, terminal (optional)
        # can be customized and scaled
        return {
            "screenshot": self.get_desktop_screenshot(),
            "terminal": self.get_terminal_output() if require_terminal else None,
        }

    def get_vm_platform(self) -> str | None:
        """
        Gets the size of the vm screen.
        """
        result = self.execute_python_command("import platform; print(platform.system())")
        if result is not None and isinstance(result, ExecuteResponse):
            return result.output.strip()
        else:
            return None

    def get_screen_size(self) -> dict[str, int] | None:
        """
        Gets the size of the vm screen.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.post(self.base_url + "/screen_size")
                if response.status_code == 200:
                    logger.info("Got screen size successfully")
                    return response.json()
                else:
                    logger.error("Failed to get screen size. Status code: %d", response.status_code)
                    logger.info("Retrying to get screen size.")
            except Exception as e:
                logger.error("An error occurred while trying to get the screen size: %s", e)
                logger.info("Retrying to get screen size.")
            time.sleep(self.retry_interval)

        logger.error("Failed to get screen size.")
        return None

    def get_vm_desktop_path(self) -> str | None:
        """
        Gets the desktop path of the vm.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.post(self.base_url + "/desktop_path")
                if response.status_code == 200:
                    logger.info("Got desktop path successfully")
                    return response.json()["desktop_path"]
                else:
                    logger.error("Failed to get desktop path. Status code: %d", response.status_code)
                    logger.info("Retrying to get desktop path.")
            except Exception as e:
                logger.error("An error occurred while trying to get the desktop path: %s", e)
                logger.info("Retrying to get desktop path.")
            time.sleep(self.retry_interval)

        logger.error("Failed to get desktop path.")
        return None

    def get_vm_directory_tree(self, path) -> dict[str, Any] | None:
        """
        Gets the directory tree of the vm.
        """
        payload = json.dumps({"path": path})

        for _ in range(self.retry_times):
            try:
                response = requests.post(
                    self.base_url + "/list_directory", headers={"Content-Type": "application/json"}, data=payload
                )
                if response.status_code == 200:
                    logger.info("Got directory tree successfully")
                    return response.json()["directory_tree"]
                else:
                    logger.error("Failed to get directory tree. Status code: %d", response.status_code)
                    logger.info("Retrying to get directory tree.")
            except Exception as e:
                logger.error("An error occurred while trying to get directory tree: %s", e)
                logger.info("Retrying to get directory tree.")
            time.sleep(self.retry_interval)

        logger.error("Failed to get directory tree.")
        return None

    # Record video
    def start_recording(self):
        """
        Starts recording the screen.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.post(self.base_url + "/start_recording")
                if response.status_code == 200:
                    logger.info("Recording started successfully")
                    return
                else:
                    logger.error("Failed to start recording. Status code: %d", response.status_code)
                    logger.info("Retrying to start recording.")
            except Exception as e:
                logger.error("An error occurred while trying to start recording: %s", e)
                logger.info("Retrying to start recording.")
            time.sleep(self.retry_interval)

        logger.error("Failed to start recording.")

    def end_recording(self, dest: str):
        """
        Ends recording the screen.
        """

        for _ in range(self.retry_times):
            try:
                response = requests.post(self.base_url + "/end_recording")
                if response.status_code == 200:
                    logger.info("Recording stopped successfully")
                    with open(dest, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return
                else:
                    logger.error("Failed to stop recording. Status code: %d", response.status_code)
                    logger.info("Retrying to stop recording.")
            except Exception as e:
                logger.error("An error occurred while trying to stop recording: %s", e)
                logger.info("Retrying to stop recording.")
            time.sleep(self.retry_interval)

        logger.error("Failed to stop recording.")

    def close(self) -> None:
        """Close the environment"""
        if self._playwright is not None:
            self._playwright.stop()
        self.provider.stop_emulator()