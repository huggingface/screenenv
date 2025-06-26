import os
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import List, Literal

from PIL import Image, ImageDraw

# SmolaAgents imports
from smolagents import CodeAgent, HfApiModel, tool
from smolagents.agent_types import AgentImage
from smolagents.memory import ActionStep, TaskStep
from smolagents.monitoring import LogLevel

# E2B imports
from screenenv import Sandbox

E2B_SYSTEM_PROMPT_TEMPLATE = """You are a desktop automation assistant that can control a remote desktop environment. The current date is <<current_date>>.

<action process>
You will be given a task to solve in several steps. At each step you will perform an action.
After each action, you'll receive an updated screenshot. 
Then you will proceed as follows, with these sections: don't skip any!

Short term goal: ...
What I see: ...
Reflection: ...
Action:
```python
click(254, 308)
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

<click_guidelines>
Look at elements on the screen to determine what to click or interact with.
The desktop has a resolution of <<resolution_x>>x<<resolution_y>> pixels, take it into account to decide clicking coordinates. NEVER USE HYPOTHETIC OR ASSUMED COORDINATES, USE TRUE COORDINATES that you can see from the screenshot.
Use precise coordinates based on the current screenshot for mouse movements and clicks. 
Whenever you click, MAKE SURE to click in the middle of the button, text, link or any other clickable element. Not under, not on the side. IN THE MIDDLE, else you risk to miss it.
In menus it is always better to click in the middle of the text rather than in the tiny icon. Calculate extremelly well the coordinates. A mistake here can make the full task fail.
Sometimes you may have missed a click, so never assume that you're on the right page, always make sure that your previous action worked.
In the screenshot you will see a green crosshair displayed over the position of your last click: this way can inspect if the mouse pointer is off of the targeted element, pay special attention to it.
</click_guidelines>

<task_resolution_example>
For a task like "Open a text editor and type 'Hello World'":
Step 1:
Short term goal: I want to open a text editor.
What I see: I am on the homepage of my desktop. I see the applications
Reflection: I think that a notes application would fit in the Applications menu, let's open it. I'll carefully click in the middle of the text 'Applications'/
Action:
```python
click(51, 8) 
```<end_code>

Step 2:
Short term goal: I want to open a text editor.
What I see: I am on the homepage of my desktop, with the applications menu open. I see an Accessories section, I see it is a section in the menu thanks to the tiny white triangle after the text accessories.
Reflection: I think that a notes application would fit the Accessories section. I SHOULD NOT try to move through the menus with scroll, it won't work:
I'll look for Accessories and click on it being very precise, clicking in the middle of the text 'Accessories'.
Action:
```python
click(76, 195) 
```<end_code>

Step 3:
Short term goal: I want to open a text editor.
What I see: I am under the Accessories menu. Under the open submenu Accessories, I've found 'Text Editor'.
Reflection: This must be my notes app. I remember that menus are navigated through clicking. I will now click on it being very precise, clicking in the middle of the text 'Text Editor'.
Action:
```python
click(251, 441) 
```<end_code>

Step 4:
Short term goal: I want to open a text editor.
What I see: I am still under the Accessories menu. Nothing has changed compared to previous screenshot. Under the open submenu Accessories, I still see 'Text Editor'. The green cross is off from the element.
Reflection: My last click must have been off. Let's correct this. I will click the correct place, right in the middle of the element.
Action:
```python
click(241, 441) 
```<end_code>

Step 5:
Short term goal: I want to type 'Hello World'.
What I see: I have opened a Notepad. The Notepad app is open on an empty page
Reflection: Now Notepad is open as intended, time to type text.
Action:
```python
type_text("Hello World")
```<end_code>

Step 6:
Short term goal: I want to type 'Hello World'.
What I see: The Notepad app displays 'Hello World'
Reflection: Now that I've 1. Opened the notepad and 2. typed 'Hello World', and 3. the result seems correct, I think the Task is completed. I will return a confirmation that the task is completed.
Action:
```python
final_answer("Done")
```<end_code>
</task_resolution_example>

<general_guidelines>
Always analyze the latest screenshot carefully before performing actions.
You can wait for appropriate loading times using the wait() tool. But don't wait forever, sometimes you've just misclicked and the process didn't launch.
Execute one action at a time: don't try to pack a click and typing in one action.
On each step, look at the last screenshot and action to validate if previous steps worked and decide the next action. If you repeated an action already without effect, it means that this action is useless: don't repeat it and try something else.
Use click to move through menus on the desktop and scroll for web and specific applications.
Always analyze the latest screenshot carefully before performing actions.
Desktop menus usually expand with more options, the tiny triangle next to some text in a menu means that menu expands. For example in Office in the Applications menu expands showing presentation or writing applications. 
NEVER CLICK THE WEB BROWSER ICON TO OPEN THE WEB BROWSER: use open_url directly.
In browser, ignore any sign-in popups while they don't interfere with the elements you want to interact with.
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


def get_agent_summary_erase_images(agent):
    for memory_step in agent.memory.steps:
        if hasattr(memory_step, "observations_images"):
            memory_step.observations_images = None
        if hasattr(memory_step, "task_images"):
            memory_step.task_images = None
    return agent.write_memory_to_messages()


class E2BVisionAgent(CodeAgent):
    """Agent for e2b desktop automation with Qwen2.5VL vision capabilities"""

    def __init__(
        self,
        model: HfApiModel,
        data_dir: str,
        desktop: Sandbox,
        tools: List[tool] = None,
        max_steps: int = 200,
        verbosity_level: LogLevel = 2,
        planning_interval: int = None,
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
        self.prompt_templates["system_prompt"] = E2B_SYSTEM_PROMPT_TEMPLATE.replace(
            "<<resolution_x>>", str(self.width)
        ).replace("<<resolution_y>>", str(self.height))

        # Add screen info to state
        self.state["screen_width"] = self.width
        self.state["screen_height"] = self.height

        # Add default tools
        self.logger.log("Setting up agent tools...")
        self._setup_desktop_tools()
        self.step_callbacks.append(self.take_screenshot_callback)

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
            self.desktop.move_mouse(x, y)
            self.desktop.left_click()
            self.click_coordinates = [x, y]
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
            self.desktop.move_mouse(x, y)
            self.desktop.right_click()
            self.click_coordinates = [x, y]
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
            self.desktop.move_mouse(x, y)
            self.desktop.double_click()
            self.click_coordinates = [x, y]
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
        def type_text(text: str) -> str:
            """
            Types the specified text at the current cursor position.
            Args:
                text: The text to type
            """
            clean_text = normalize_text(text)
            self.desktop.write(clean_text, delay_in_ms=75)
            self.logger.log(f"Typed text: '{clean_text}'")
            return f"Typed text: '{clean_text}'"

        @tool
        def press_key(key: str) -> str:
            """
            Presses a keyboard key
            Args:
                key: The key to press (e.g. "enter", "space", "backspace", etc.).
            """
            self.desktop.press(key)
            self.logger.log(f"Pressed key: {key}")
            return f"Pressed key: {key}"

        @tool
        def go_back() -> str:
            """
            Goes back to the previous page in the browser. If using this tool doesn't work, just click the button directly.
            Args:
            """
            self.desktop.press(["alt", "left"])
            self.logger.log("Went back one page")
            return "Went back one page"

        @tool
        def drag_and_drop(x1: int, y1: int, x2: int, y2: int) -> str:
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
        def open_url(url: str) -> str:
            """
            Directly opens a browser with the specified url: use this at start of web searches rather than trying to click the browser.
            Args:
                url: The URL to open
            """
            # Make sure URL has http/https prefix
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            self.desktop.open(url)
            # Give it time to load
            time.sleep(2)
            self.logger.log(f"Opening URL: {url}")
            return f"Opened URL: {url}"

        @tool
        def find_on_page_ctrl_f(search_string: str) -> str:
            """
            Scroll the browser viewport to the first occurrence of the search string. This is equivalent to Ctrl+F. Use this to search on a pdf for instance.
            Args:
                search_string: The string to search for on the page.
            """
            self.desktop.press(["ctrl", "f"])
            time.sleep(0.3)
            clean_text = normalize_text(search_string)
            self.desktop.write(clean_text, delay_in_ms=75)
            time.sleep(0.3)
            self.desktop.press("enter")
            time.sleep(0.3)
            self.desktop.press("esc")
            output_message = f"Scrolled to the first occurrence of '{clean_text}'"
            self.logger.log(output_message)
            return output_message

        # Register the tools
        self.tools["click"] = click
        self.tools["right_click"] = right_click
        self.tools["double_click"] = double_click
        self.tools["move_mouse"] = move_mouse
        self.tools["type_text"] = type_text
        self.tools["press_key"] = press_key
        self.tools["scroll"] = scroll
        self.tools["wait"] = wait
        self.tools["open_url"] = open_url
        self.tools["go_back"] = go_back
        self.tools["drag_and_drop"] = drag_and_drop
        self.tools["find_on_page_ctrl_f"] = find_on_page_ctrl_f

    def take_screenshot_callback(self, memory_step: ActionStep, agent=None) -> None:
        """Callback that takes a screenshot + memory snapshot after a step completes"""
        self.logger.log("Analyzing screen content...")

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
                and previous_memory_step.step_number <= current_step - 1
            ):
                previous_memory_step.observations_images = None
            elif isinstance(previous_memory_step, TaskStep):
                previous_memory_step.task_images = None

            if (
                isinstance(previous_memory_step, ActionStep)
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
                        memory_step.observations += "\nWARNING: You've executed the same action several times in a row. MAKE SURE TO NOT UNNECESSARILY REPEAT ACTIONS."

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
