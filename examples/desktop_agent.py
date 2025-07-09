import os
import time
import unicodedata
from typing import List, Literal

# SmolaAgents imports
from smolagents import Model, Tool, tool
from smolagents.monitoring import LogLevel

# ScreenEnv imports
from screenenv import DesktopAgentBase, Sandbox

from .utils import get_user_input


class CustomDesktopAgent(DesktopAgentBase):
    """Agent for desktop automation"""

    def __init__(
        self,
        model: Model,
        data_dir: str,
        desktop: Sandbox,
        tools: List[Tool] | None = None,
        max_steps: int = 200,
        verbosity_level: LogLevel = LogLevel.INFO,
        planning_interval: int | None = None,
        use_v1_prompt: bool = False,
        **kwargs,
    ):
        super().__init__(
            model=model,
            data_dir=data_dir,
            desktop=desktop,
            tools=tools,
            max_steps=max_steps,
            verbosity_level=verbosity_level,
            planning_interval=planning_interval,
            use_v1_prompt=use_v1_prompt,
            **kwargs,
        )

        # OPTIONAL: Add a custom prompt template - see src/screenenv/desktop_agent/desktop_agent_base.py for more details about the default prompt template
        # self.prompt_templates["system_prompt"] = CUSTOM_PROMPT_TEMPLATE.replace(
        #     "<<resolution_x>>", str(self.width)
        # ).replace("<<resolution_y>>", str(self.height))
        # Important: Change the prompt to get better results, depending on your action space.

    def _setup_desktop_tools(self):
        """Register all desktop tools"""

        @tool
        def click(x: int, y: int) -> str:
            """
            Performs a left-click at the specified coordinates
            Args:
                x: The x coordinate (horizontal position)
                y: The y coordinate (vertical position)
            """
            self.desktop.left_click(x, y)
            self.click_coordinates = (x, y)
            self.logger.log(f"Clicked at coordinates ({x}, {y})")
            return f"Clicked at coordinates ({x}, {y})"

        @tool
        def right_click(x: int, y: int) -> str:
            """
            Performs a right-click at the specified coordinates
            Args:
                x: The x coordinate (horizontal position)
                y: The y coordinate (vertical position)
            """
            self.desktop.right_click(x, y)
            self.click_coordinates = (x, y)
            self.logger.log(f"Right-clicked at coordinates ({x}, {y})")
            return f"Right-clicked at coordinates ({x}, {y})"

        @tool
        def double_click(x: int, y: int) -> str:
            """
            Performs a double-click at the specified coordinates
            Args:
                x: The x coordinate (horizontal position)
                y: The y coordinate (vertical position)
            """
            self.desktop.double_click(x, y)
            self.click_coordinates = (x, y)
            self.logger.log(f"Double-clicked at coordinates ({x}, {y})")
            return f"Double-clicked at coordinates ({x}, {y})"

        @tool
        def move_mouse(x: int, y: int) -> str:
            """
            Moves the mouse cursor to the specified coordinates
            Args:
                x: The x coordinate (horizontal position)
                y: The y coordinate (vertical position)
            """
            self.desktop.move_mouse(x, y)
            self.logger.log(f"Moved mouse to coordinates ({x}, {y})")
            return f"Moved mouse to coordinates ({x}, {y})"

        def normalize_text(text):
            return "".join(
                c
                for c in unicodedata.normalize("NFD", text)
                if not unicodedata.combining(c)
            )

        @tool
        def write(text: str) -> str:
            """
            Types the specified text at the current cursor position.
            Args:
                text: The text to type
            """
            # clean_text = normalize_text(text)
            self.desktop.write(text, delay_in_ms=10)
            self.logger.log(f"Typed text: '{text}'")
            return f"Typed text: '{text}'"

        @tool
        def press(key: str) -> str:
            """
            Presses a keyboard key or combination of keys
            Args:
                key: The key to press (e.g. "enter", "space", "backspace", etc.) or a multiple keys string to press, for example "ctrl+a" or "ctrl+shift+a".
            """
            self.desktop.press(key)
            self.logger.log(f"Pressed key: {key}")
            return f"Pressed key: {key}"

        @tool
        def drag(x1: int, y1: int, x2: int, y2: int) -> str:
            """
            Clicks [x1, y1], drags mouse to [x2, y2], then release click.
            Args:
                x1: origin x coordinate
                y1: origin y coordinate
                x2: end x coordinate
                y2: end y coordinate
            """
            self.desktop.drag((x1, y1), (x2, y2))
            message = f"Dragged and dropped from [{x1}, {y1}] to [{x2}, {y2}]"
            self.logger.log(message)
            return message

        @tool
        def scroll(
            x: int, y: int, direction: Literal["up", "down"] = "down", amount: int = 2
        ) -> str:
            """
            Moves the mouse to selected coordinates, then uses the scroll button: this could scroll the page or zoom, depending on the app. DO NOT use scroll to move through linux desktop menus.
            Args:
                x: The x coordinate (horizontal position) of the element to scroll/zoom
                y: The y coordinate (vertical position) of the element to scroll/zoom
                direction: The direction to scroll ("up" or "down"), defaults to "down". For zoom, "up" zooms in, "down" zooms out.
                amount: The amount to scroll. A good amount is 1 or 2.
            """
            self.desktop.move_mouse(x, y)
            self.desktop.scroll(direction=direction, amount=amount)
            message = f"Scrolled {direction} by {amount}"
            self.logger.log(message)
            return message

        @tool
        def wait(seconds: float) -> str:
            """
            Waits for the specified number of seconds. Very useful in case the prior order is still executing (for example starting very heavy applications like browsers or office apps)
            Args:
                seconds: Number of seconds to wait, generally 3 is enough.
            """
            time.sleep(seconds)
            self.logger.log(f"Waited for {seconds} seconds")
            return f"Waited for {seconds} seconds"

        @tool
        def open(file_or_url: str) -> str:
            """
            Directly opens a browser with the specified url or opens a file with the default application: use this at start of web searches rather than trying to click the browser or open a file by clicking.
            Args:
                file_or_url: The URL or file to open
            """

            self.desktop.open(file_or_url)
            # Give it time to load
            time.sleep(2)
            self.logger.log(f"Opening: {file_or_url}")
            return f"Opened: {file_or_url}"

        @tool
        def launch_app(app_name: str) -> str:
            """
            Launches the specified application.
            Args:
                app_name: the name of the application to launch
            """
            self.desktop.launch(app_name)
            self.logger.log(f"Launched app: {app_name}")
            return f"Launched app: {app_name}"

        @tool
        def execute(command: str) -> str:
            """
            Executes a terminal command in the desktop environment.
            Args:
                command: The command to execute
            """
            self.desktop.execute_command(command)
            self.logger.log(f"Executed command: {command}")
            return f"Executed command: {command}"

        @tool
        def refresh() -> str:
            """
            Refreshes the current web page if you're in a browser.
            """
            self.desktop.press(["ctrl", "r"])
            self.logger.log("Refreshed the current page")
            return "Refreshed the current page"

        @tool
        def go_back() -> str:
            """
            Goes back to the previous page in the browser. If using this tool doesn't work, just click the button directly.
            Args:
            """
            self.desktop.press(["alt", "left"])
            self.logger.log("Went back one page")
            return "Went back one page"

        # Register the tools
        self.tools["click"] = click
        self.tools["right_click"] = right_click
        self.tools["double_click"] = double_click
        self.tools["move_mouse"] = move_mouse
        self.tools["write"] = write
        self.tools["press"] = press
        self.tools["scroll"] = scroll
        self.tools["wait"] = wait
        self.tools["open"] = open
        self.tools["go_back"] = go_back
        self.tools["drag"] = drag
        self.tools["launch_app"] = launch_app
        self.tools["execute"] = execute
        self.tools["refresh"] = refresh


if __name__ == "__main__":
    # ================================
    # MODEL CONFIGURATION
    # ================================

    from smolagents import OpenAIServerModel

    model = OpenAIServerModel(
        model_id="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # For Inference Endpoints
    # from smolagents import HfApiModel
    # model = HfApiModel(
    #     model_id="Qwen/Qwen2.5-VL-72B-Instruct",
    #     token=os.getenv("HF_TOKEN"),
    #     provider="nebius",
    # )

    # For Transformer models
    # from smolagents import TransformersModel
    # model = TransformersModel(
    #     model_id="Qwen/Qwen2.5-VL-72B-Instruct",
    #     device_map="auto",
    #     torch_dtype="auto",
    #     trust_remote_code=True,
    # )

    # For other providers
    # from smolagents import LiteLLMModel
    # model = LiteLLMModel(model_id="anthropic/claude-sonnet-4-20250514")

    # ================================
    # RUN AGENT
    # ================================

    # Interactive task input loop
    sandbox = None
    agent = None
    while True:
        try:
            task = get_user_input()
            if task is None:
                exit()
            sandbox = Sandbox(headless=False, resolution=(1280, 700))
            sandbox.start_recording()
            agent = CustomDesktopAgent(model=model, data_dir="data", desktop=sandbox)

            print("\n🤖 Agent is working on your task...")
            print("-" * 60)
            result = agent.run(task)
            print("\n✅ Task completed successfully!")
            print(f"📄 Result: {result}")
        except Exception as e:
            print(f"\n❌ Error occurred: {str(e)}")
        finally:
            if sandbox:
                sandbox.end_recording("recording.mp4")
            if agent:
                agent.close()

        print("\n" + "=" * 60)
