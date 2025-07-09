import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import List

from PIL import Image, ImageDraw

# SmolaAgents imports
from smolagents import CodeAgent, Model, Tool
from smolagents.agent_types import AgentImage
from smolagents.memory import ActionStep, TaskStep
from smolagents.monitoring import LogLevel

# ScreenEnv imports
from ..sandbox import Sandbox

DESKTOP_SYSTEM_PROMPT_TEMPLATE = """You are a desktop automation assistant that can control a remote desktop environment. The current date is <<current_date>>.

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
- **Text editing**: Focus field shortcut (or `click` if you can't use shortcuts).
- **Dialog handling**: Press `Enter` to confirm, `Escape` to cancel
- **Application switching**: `Alt+Tab` or click taskbar items
- **Menu navigation**: Follow the hierarchy, look for visual cues
- **Popup handling**: MOST OF THE TIME, IF A POPUP WINDOW APPEARS in the center of the screen (e.g. cookie consent, etc.), TRY TO USE `press("enter")` TO CONFIRM OR `press("escape")` TO CANCEL TO CLOSE IT.

### Text Editor Guidelines (e.g. LibreOffice Writer)
- Use a focus field shortcut, or click() if shortcuts aren’t available.
- In text editor software, USE press('enter') TO INSERT NEW LINE. DON'T USE write('\n').
  Follow the pattern: <write("content"), press('enter')> to write multi-line text in a single execution.
  For example, Use:
  ```python
  write("Hello World")
  press('enter')
  press('enter')
  write("Hello World")
  ```
  DON'T USE CHARACTERS '\n' into the write() function. USE instead press('enter').
- You can generate full text by writing the code in a single execution.
- Ensure the final text is well formatted (with titles, sub-titles, etc.), attractive and easy to read — aim for clear and visually appealing presentation.
- In most of cases, separate the text into paragraphs by using two press('enter') to insert two new lines.
- the second argument of `write` is the delay in milliseconds. use around 10ms.

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


class DesktopAgentBase(CodeAgent, ABC):
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
        self.prompt_templates["system_prompt"] = DESKTOP_SYSTEM_PROMPT_TEMPLATE.replace(
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

    @abstractmethod
    def _setup_desktop_tools(self) -> None:
        """Register all desktop tools"""

        # Example of a agent tool that can be used to click on the screen
        # @tool
        # def click(x: int, y: int) -> str:
        #     """
        #     Performs a left-click at the specified coordinates
        #     Args:
        #         x: The x coordinate (horizontal position)
        #         y: The y coordinate (vertical position)
        #     """
        #     self.desktop.left_click(x, y)
        #     self.click_coordinates = (x, y)
        #     self.logger.log(f"Clicked at coordinates ({x}, {y})")
        #     return f"Clicked at coordinates ({x}, {y})"

        # # Register the tools
        # self.tools["click"] = click

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

        if self.click_coordinates is not None:
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
