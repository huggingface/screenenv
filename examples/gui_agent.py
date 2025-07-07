import os
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import List, Literal

from PIL import Image, ImageDraw

# SmolaAgents imports
from smolagents import CodeAgent, Model, Tool, tool
from smolagents.agent_types import AgentImage
from smolagents.memory import ActionStep, TaskStep
from smolagents.monitoring import LogLevel

# ScreenEnv imports
from screenenv import Sandbox

from .utils import get_user_input

GUI_SYSTEM_PROMPT_TEMPLATE = """You are a desktop automation assistant that can control a remote desktop environment. The current date is <<current_date>>.

<action process>
You will be given a task to solve in several steps. At each step you will perform an action.
After each action, you'll receive an updated screenshot.
Then you will proceed as follows, with these sections: don't skip any!

Short term goal: ...
What I see: ...
Reflection: ...
Action:
```python
tool_name(arguments)
```<end_code>

Akways format your action ('Action:' part) as Python code blocks as shown above.
</action_process>

<tools>
On top of performing computations in the Python code snippets that you create, you only have access to these tools to interact with the desktop, no additional ones:
{%- for tool in tools.values() %}
- {{ tool.name }}: {{ tool.description }}
    Takes inputs: {{tool.inputs}}
    Returns an output of type: {{tool.output_type}}
{%- endfor %}
</tools>

<gui_guidelines>
Look at elements on the screen to determine what to click or interact with.
The desktop has a resolution of <<resolution_x>>x<<resolution_y>> pixels, take it into account to decide mouse interaction coordinates. NEVER USE HYPOTHETIC OR ASSUMED COORDINATES, USE TRUE COORDINATES that you can see from the screenshot.
Use precise coordinates based on the current screenshot for mouse interaction.
</gui_guidelines>

<task_resolution_example>
For a task like "Open a text editor and write 'Hello World'":
Step 1:
Short term goal: I want to open a text editor.
What I see: I am on the homepage of my desktop.
Reflection: I think that a notes application would fit in the Applications menu, let's open it.
Action:
```python
launch_app("libreoffice --writer")
wait(3)
```<end_code>


Step 2:
Short term goal: I want to write 'Hello World'.
What I see: I see a popup appearing.
Reflection: I see a popup appearing. I will press 'enter' to confirm.
Action:
```python
press("enter")
```<end_code>
</task_resolution_example>

Step 3:
Short term goal: I want to write 'Hello World'.
What I see: I have opened a Notepad. The Notepad app is open on an empty page
Reflection: Now Notepad is open as intended, time to write text.
Action:
```python
write("Hello World")
```<end_code>

Step 4:
Short term goal: I want to write 'Hello World'.
What I see: The Notepad app displays 'Hello World'
Reflection: Now that I've 1. Opened the notepad and 2. wrote 'Hello World', and 3. the result seems correct, I think the Task is completed. I will return a confirmation that the task is completed.
Action:
```python
final_answer("Done")
```<end_code>
</task_resolution_example>

<general_guidelines>
# GUI Agent Guidelines for XFCE4 Ubuntu

## Environment Overview
The sandbox uses Ubuntu 22.04 with XFCE4 desktop environment, accessible via VNC. Key software includes:
- XFCE4 desktop environment
- Google Chrome/Chromium browser
- LibreOffice suite
- Standard Ubuntu applications

## Available Tools
- **Navigation**: `click`, `right_click`, `double_click`, `move_mouse`, `drag`
- **Input**: `write`, `press`, `scroll`
- **Applications**: `open`, `launch_app`, `execute`
- **Browser**: `go_back`, `refresh`
- **Utility**: `wait`

## Core Principles

### 1. Screenshot Analysis
- **Always analyze the latest screenshot carefully before performing actions**
- Validate that previous actions worked by examining the current state
- If an action didn't produce the expected result, don't repeat it - try an alternative approach

### 2. Action Execution
- **Execute one action at a time** - don't combine multiple actions in a single step
- Wait for appropriate loading times using `wait()`, but don't wait indefinitely
- If you've repeated an action without effect, it's likely useless - try something else

### 3. Application Management
- **Use `open()` for files and URLs** - don't click browser icons
- **Use `launch_app()` for applications** - more reliable than GUI navigation
- **Never click the web browser icon** - use `open()` with URLs directly

### 4. Keyboard Shortcuts Priority
- **Prefer keyboard shortcuts over GUI actions when possible**
- Common shortcuts:
  - `ctrl+S` for save
  - `ctrl+C` for copy
  - `ctrl+V` for paste
  - `trl+Z` for undo
  - `ctrl+A` for select all
  - `enter` to confirm dialogs/popups
  - `escape` to cancel/close
  - `alt+tab` to switch applications
  - `ctrl+T` for new tab (browsers)
  - `ctrl+W` to close tab/window

### 5. Navigation Strategies
- **Desktop menus**: Use `click` to navigate through menu hierarchies
- **Web content**: Use `scroll` for navigation within pages
- **Menu expansion**: Look for small triangles (►) indicating expandable menus
- **Context menus**: Use `right_click` to access additional options

### 6. XFCE4 Specific Behaviors
- Desktop menus usually expand with more options when clicked
- The Applications menu has hierarchical structure (Office → Writer/Calc/etc.)
- Panel items respond to both left and right clicks
- Window management via title bars and panel

### 7. Browser Interactions
- Ignore sign-in popups unless they block required elements
- Use `refresh()` if page doesn't load properly
- Use `go_back()` for navigation history
- Prefer `open()` with URLs over manual address bar typing

### 8. Error Recovery
- If clicking doesn't work, try `double_click` or `right_click`
- If typing doesn't appear, ensure the correct field is focused with `click`
- If applications don't launch, try `execute()` with command line
- If interface seems frozen, try pressing `Escape` or `Alt+Tab`

### 9. Common Patterns
- **File operations**: Use file manager or `open()` with file paths
- **Text editing**: Focus field shortcut (or `click` if you can't use shortcuts), then `write`. In Text editors press('enter') to write a new line. So generate <write("content"), press('enter')> pattern for write a entiere text in one code execution. For example, if you want to `write("Hello World\n\nHello World")`, generate instead `write("Hello World")`, then `press('enter')`, then `press('enter')`, then `write("Hello World")`.
- **Dialog handling**: Press `Enter` to confirm, `Escape` to cancel
- **Application switching**: `Alt+Tab` or click taskbar items
- **Menu navigation**: Follow the hierarchy, look for visual cues
- **Popup handling**: MOST OF THE TIME, IF A POPUP WINDOW APPEARS in the center of the screen (e.g. cookie consent, etc.), TRY TO USE `press("enter")` TO CONFIRM OR `press("escape")` TO CANCEL TO CLOSE IT.

### 10. Troubleshooting
- If action seems to have no effect, wait briefly and check screenshot
- If interface becomes unresponsive, try keyboard shortcuts
- If applications crash, use `launch_app()` to restart
- If text doesn't appear when typing, click the input field first
- MOST OF THE TIME, IF A POPUP WINDOW APPEARS, TRY TO USE `press("enter")` TO CONFIRM OR `press("escape")` TO CANCEL TO CLOSE IT.
- If you want to close the current window, use `press("ctrl+w")`
</general_guidelines>
""".replace("<<current_date>>", datetime.now().strftime("%A, %d-%B-%Y"))


def draw_marker_on_image(image_copy, click_coordinates):
    x, y = click_coordinates
    draw = ImageDraw.Draw(image_copy)
    cross_size, linewidth = 10, 3
    # Draw cross
    draw.line((x - cross_size, y, x + cross_size, y), fill="green", width=linewidth)
    draw.line((x, y - cross_size, x, y + cross_size), fill="green", width=linewidth)
    # Add a circle around it for better visibility
    draw.ellipse(
        (
            x - cross_size * 2,
            y - cross_size * 2,
            x + cross_size * 2,
            y + cross_size * 2,
        ),
        outline="green",
        width=linewidth,
    )
    return image_copy


# def get_agent_summary_erase_images(agent: CodeAgent) -> str:
#     for memory_step in agent.memory.steps:
#         if hasattr(memory_step, "observations_images"):
#             memory_step.observations_images = None
#         if hasattr(memory_step, "task_images"):
#             memory_step.task_images = None
#     return agent.write_memory_to_messages()


class GUIAgent(CodeAgent):
    """Agent for e2b desktop automation with Qwen2.5VL vision capabilities"""

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
        self.desktop = desktop
        self.data_dir = data_dir
        self.planning_interval = planning_interval
        # Initialize Desktop
        self.width, self.height = self.desktop.get_screen_size()
        print(f"Screen size: {self.width}x{self.height}")

        # Set up temp directory
        os.makedirs(self.data_dir, exist_ok=True)
        print(f"Screenshots and steps will be saved to: {self.data_dir}")

        self.use_v1_prompt = use_v1_prompt
        # Initialize base agent
        super().__init__(
            tools=tools or [],
            model=model,
            max_steps=max_steps,
            verbosity_level=verbosity_level,
            planning_interval=self.planning_interval,
            stream_outputs=True,
            **kwargs,
        )
        self.prompt_templates["system_prompt"] = GUI_SYSTEM_PROMPT_TEMPLATE.replace(
            "<<resolution_x>>", str(self.width)
        ).replace("<<resolution_y>>", str(self.height))

        # Add screen info to state
        self.state["screen_width"] = self.width
        self.state["screen_height"] = self.height

        # Add default tools
        self.logger.log("Setting up agent tools...")
        self._setup_desktop_tools()
        self.step_callbacks.append(self.take_screenshot_callback)
        self.click_coordinates: tuple[int, int] | None = None

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

    def take_screenshot_callback(
        self, memory_step: ActionStep, agent: CodeAgent
    ) -> None:
        """Callback that takes a screenshot + memory snapshot after a step completes"""
        self.logger.log("Analyzing screen content...")

        assert memory_step.step_number is not None

        current_step = memory_step.step_number

        time.sleep(2.5)  # Let things happen on the desktop
        screenshot_bytes = self.desktop.screenshot()
        image = Image.open(BytesIO(screenshot_bytes))

        # Create a filename with step number
        screenshot_path = os.path.join(self.data_dir, f"step_{current_step:03d}.png")
        image.save(screenshot_path)

        image_copy = image.copy()

        if getattr(self, "click_coordinates", None):
            print("DRAWING MARKER")
            image_copy = draw_marker_on_image(image_copy, self.click_coordinates)

        self.last_marked_screenshot = AgentImage(screenshot_path)
        print(f"Saved screenshot for step {current_step} to {screenshot_path}")

        for previous_memory_step in (
            agent.memory.steps
        ):  # Remove previous screenshots from logs for lean processing
            if (
                isinstance(previous_memory_step, ActionStep)
                and previous_memory_step.step_number is not None
                and previous_memory_step.step_number <= current_step - 1
            ):
                previous_memory_step.observations_images = None
            elif isinstance(previous_memory_step, TaskStep):
                previous_memory_step.task_images = None

            if (
                isinstance(previous_memory_step, ActionStep)
                and previous_memory_step.step_number is not None
                and previous_memory_step.step_number == current_step - 1
            ):
                if (
                    previous_memory_step.tool_calls
                    and getattr(previous_memory_step.tool_calls[0], "arguments", None)
                    and memory_step.tool_calls
                    and getattr(memory_step.tool_calls[0], "arguments", None)
                ):
                    if (
                        previous_memory_step.tool_calls[0].arguments
                        == memory_step.tool_calls[0].arguments
                    ):
                        memory_step.observations = (
                            (
                                memory_step.observations
                                + "\nWARNING: You've executed the same action several times in a row. MAKE SURE TO NOT UNNECESSARILY REPEAT ACTIONS."
                            )
                            if memory_step.observations
                            else (
                                "\nWARNING: You've executed the same action several times in a row. MAKE SURE TO NOT UNNECESSARILY REPEAT ACTIONS."
                            )
                        )

        # Add the marker-edited image to the current memory step
        memory_step.observations_images = [image_copy]

        # memory_step.observations_images = [screenshot_path] # IF YOU USE THIS INSTEAD OF ABOVE, LAUNCHING A SECOND TASK BREAKS

        self.click_coordinates = None  # Reset click marker

    def close(self):
        """Clean up resources"""
        if self.desktop:
            print("Killing sandbox...")
            self.desktop.kill()
            print("Sandbox terminated")


if __name__ == "__main__":
    from smolagents import OpenAIServerModel

    # ================================
    # MODEL CONFIGURATION
    # ================================

    model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # For Inference Endpoints
    # from smolagents import HfApiModel
    # model = HfApiModel(
    #     model_id="Qwen/Qwen2.5-VL-7B-Instruct",
    #     token=os.getenv("HF_TOKEN"),
    #     provider="fireworks-ai",
    # )

    # For Transformer models
    # from smolagents import TransformersModel
    # model = TransformersModel(
    #     model_id="Qwen/Qwen2.5-VL-7B-Instruct",
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
    while True:
        try:
            task = get_user_input()
            sandbox = Sandbox(headless=False)
            sandbox.start_recording()
            agent = GUIAgent(
                model=model, data_dir="data", desktop=Sandbox(headless=False)
            )
            if task is None:
                break

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
            agent.close()

        print("\n" + "=" * 60)
