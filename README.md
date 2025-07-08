# ScreenEnv

A powerful Python library for creating and managing isolated desktop environments using Docker containers. ScreenEnv provides a sandboxed Ubuntu desktop environment with XFCE4 that you can programmatically control for GUI automation, testing, and development.

## Features

- 🖥️ **Isolated Desktop Environment**: Full Ubuntu desktop with XFCE4 running in Docker
- 🎮 **GUI Automation**: Complete mouse and keyboard control
- 🌐 **Web Automation**: Built-in browser automation with Playwright
- 📹 **Screen Recording**: Capture video recordings of all actions
- 📸 **Screenshot Capabilities**: Desktop and browser screenshots
- 🖱️ **Mouse Control**: Click, drag, scroll, and mouse movement
- ⌨️ **Keyboard Input**: Text typing and key combinations
- 🪟 **Window Management**: Launch, activate, and close applications
- 📁 **File Operations**: Upload, download, and file management
- 🐚 **Terminal Access**: Execute commands and capture output
- 🤖 **MCP Server Support**: Model Context Protocol integration for AI/LLM automation
- 🐳 **Docker Ready**: Pre-built Docker image with all dependencies

## Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd screenenv
   ```

2. **Install the package** (choose one):

   **latest release:**
   ```bash
   pip install screenenv
   # or
   uv pip install screenenv
   ```

   **from source:**
   ```bash
   pip install .
   # or
   uv sync
   ```


### Basic Usage

```python
from screenenv import Sandbox

# Create a sandbox environment
sandbox = Sandbox()

try:
    # Launch a terminal
    sandbox.launch("xfce4-terminal")

    # Type some text
    sandbox.write("echo 'Hello from ScreenEnv!'")
    sandbox.press("Enter")

    # Take a screenshot
    screenshot = sandbox.screenshot()
    with open("screenshot.png", "wb") as f:
        f.write(screenshot)

finally:
    # Clean up
    sandbox.close()
```

> For usage, see the source code in `examples/sandbox_demo.py`

## MCP Server Support

ScreenEnv includes full support for the Model Context Protocol (MCP), enabling seamless integration with AI/LLM systems for desktop automation.

### What is MCP?

The Model Context Protocol (MCP) is a standard for AI assistants to interact with external tools and data sources. ScreenEnv's MCP server provides desktop automation capabilities that can be used by any MCP-compatible AI system.

### MCP Server Features

- **30+ Automation Tools**: Complete desktop control via MCP
- **Streamable HTTP Transport**: Efficient communication protocol

### Starting the MCP Server

```python
from screenenv import MCPRemoteServer

# Start MCP server
server = MCPRemoteServer()

print(f"MCP Server URL: {server.server_url}")
print(f"Server Configuration: {server.mcp_server_json}")
```

### MCP Client Usage

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from screenenv import MCPRemoteServer

async def mcp_automation():
    # Start MCP server
    server = MCPRemoteServer(headless=False)

    try:
        # Connect to MCP server
        async with streamablehttp_client(server.server_url) as (
            read_stream, write_stream, _
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Launch terminal
                await session.call_tool("launch", {
                    "application": "xfce4-terminal",
                    "wait_for_window": True
                })

                # Type commands
                await session.call_tool("write", {"text": "echo 'Hello MCP!'"})
                await session.call_tool("press", {"key": ["Enter"]})

                # Take screenshot
                response = await session.call_tool("screenshot", {})
                screenshot_base64 = response.content[0].data

                screenshot_bytes = base64.b64decode(screenshot_base64)
                image = Image.open(io.BytesIO(screenshot_bytes))
                image.save("screenshot.png")
                ...

                print("MCP automation completed!")

    finally:
        server.close()

# Run the automation
asyncio.run(mcp_automation())
```

### Available MCP Tools

#### System Operations
- `execute_command` - Execute shell commands
- `get_platform` - Get system platform information
- `get_screen_size` - Get screen dimensions
- `get_desktop_path` - Get desktop directory path
- `get_directory_tree` - List directory contents
- `get_file` - Get file contents
- `download_file` - Download file from URL
- `start_recording` - Start screen recording
- `end_recording` - End screen recording

#### Application Management
- `wait` - Wait for specified milliseconds
- `open` - Open file or URL
- `launch` - Launch application
- `get_current_window_id` - Get current window ID
- `get_application_windows` - Get windows for application
- `get_window_name` - Get window name/title
- `get_window_size` - Get window size
- `activate_window` - Activate window
- `close_window` - Close window
- `get_terminal_output` - Get terminal output

#### GUI Automation
- `screenshot` - Take screenshot
- `left_click` - Left click at coordinates
- `double_click` - Double click at coordinates
- `right_click` - Right click at coordinates
- `middle_click` - Middle click at coordinates
- `scroll` - Scroll mouse wheel
- `move_mouse` - Move mouse to coordinates
- `mouse_press` - Press mouse button
- `mouse_release` - Release mouse button
- `get_cursor_position` - Get cursor position
- `write` - Type text
- `press` - Press keys
- `drag` - Drag mouse from one position to another

### MCP Server Configuration

```python
# Advanced MCP server configuration
server = MCPRemoteServer(
    os_type="Ubuntu",
    provider_type="docker",
    headless=True,
    resolution=(1920, 1080),
    disk_size="32G",
    ram_size="4G",
    cpu_cores="4",
    session_password="your_password",
    stream_server=True,
    dpi=96,
    timeout=1000
)
```

## Sandbox Instantiation

### Basic Configuration

```python
from screenenv import Sandbox

# Minimal configuration
sandbox = Sandbox()

# With custom settings
sandbox = Sandbox(
    os_type="Ubuntu",           # Currently only Ubuntu is supported
    provider_type="docker",     # Currently only Docker is supported
    headless=True,              # Run without VNC viewer
    screen_size="1920x1080",    # Desktop resolution
    volumes=[],                 # Docker volumes to mount
    auto_ssl=False             # Enable SSL for VNC (experimental)
)
```

## Core Features

### Mouse Control

```python
# Click operations
sandbox.left_click(x=100, y=200)
sandbox.right_click(x=300, y=400)
sandbox.double_click(x=500, y=600)

# Mouse movement
sandbox.move_mouse(x=800, y=900)

# Drag and drop
sandbox.drag(fr=(100, 100), to=(200, 200))

# Scrolling
sandbox.scroll(direction="down", amount=3)

sandbox.mouse_release(button="left")

sandbox.mouse_press(button="left")
sandbox.mouse_release(button="left")
```

### Keyboard Input

```python
# Type text
sandbox.write("Hello, World!", delay_in_ms=50)

# Key combinations
sandbox.press(["Ctrl", "C"])  # Copy
sandbox.press(["Ctrl", "V"])  # Paste
sandbox.press(["Alt", "Tab"]) # Switch windows
sandbox.press("Enter")        # Single key
```

### Application Management

```python
# Launch applications
sandbox.launch("xfce4-terminal")
sandbox.launch("libreoffice --writer")
sandbox.open("https://www.google.com")

# Window management
windows = sandbox.get_application_windows("xfce4-terminal")
window_id = windows[0]
sandbox.activate_window(window_id)

window_id = sandbox.get_current_window_id() # get the current activate window id.
sandbox.window_size(window_id)
sandbox.get_window_title(window_id)
sandbox.close_window(window_id)
```

### File Operations

```python
# Upload files to sandbox
sandbox.upload_file_to_remote("local_file.txt", "/home/user/remote_file.txt")

# Download files from sandbox
sandbox.download_file_from_remote("/home/user/remote_file.txt", "local_file.txt")

# Download from URL
sandbox.download_url_file_to_remote("https://example.com/file.txt", "/home/user/file.txt")
```

### Screenshots and Recording

```python
# Start recording
sandbox.start_recording()

# Take screenshots
desktop_screenshot = sandbox.desktop_screenshot()

# Stop recording and save it locally to a file 'demo.mp4'
sandbox.end_recording("demo.mp4")
```

### Terminal Operations

```python
# Execute commands
response = sandbox.execute_command("ls -la")
print(response.output)

# Python commands
response = sandbox.execute_python_command("print('Hello')", ["os"])
print(response.output)

# Get terminal output
output = sandbox.get_terminal_output() # Only if a desktop terminal application is running. To get command output, use execute_command() instead.
```

## Examples

### Complete GUI Automation Demo

```python
from screenenv import Sandbox
import time

def demo_automation():
    sandbox = Sandbox(headless=False)

    try:
        # Launch terminal
        sandbox.launch("xfce4-terminal")
        time.sleep(2)

        # Type commands
        sandbox.write("echo 'Starting automation demo'")
        sandbox.press("Enter")

        # Open web browser
        sandbox.open("https://www.python.org")
        time.sleep(3)

        # Take screenshot
        screenshot = sandbox.screenshot()
        with open("demo_screenshot.png", "wb") as f:
            f.write(screenshot)

    finally:
        sandbox.close()

if __name__ == "__main__":
    demo_automation()
```

### Web Automation with Playwright

```python
from screenenv import Sandbox

def web_automation():
    sandbox = Sandbox(headless=True)

    try:
        # Open website
        sandbox.open("https://www.example.com")

        # Take browser screenshot
        screenshot = sandbox.playwright_screenshot(full_page=True)
        with open("web_screenshot.png", "wb") as f:
            f.write(screenshot)

        playwright_browser = sandbox.playwright_browser()

    finally:
        sandbox.close()
```
### Benefits

- **Single Entry Point**: All services accessible through one port
- **Clean URLs**: Organized by service type (`/api`, `/novnc`, `/browser`, `/mcp`)
- **Load Balancing Ready**: Easy to add multiple backend instances

## MCP Server Demo

```bash
python -m examples.mcp_server_demo # or sudo -E python -m examples.mcp_server_demo if not in docker group
```

## Sandbox Demo

```bash
python -m examples.sandbox_demo # or sudo -E python -m examples.sandbox_demo if not in docker group
```

## Computer Agent Demo

```bash
cd examples/computer_agent
python app.py # or sudo -E python app.py if not in docker group
```


## System Requirements

- **Docker**: Must be installed and running
- **Python**: 3.10 or higher
- **Playwright**: For web automation features
- **Memory**: At least 4GB RAM recommended

## Docker Image

The sandbox uses a custom Ubuntu 22.04 Docker image with:
- XFCE4 desktop environment
- VNC server for remote access
- Google Chrome/Chromium browser
- LibreOffice suite
- Python development tools
- MCP server support
- Nginx reverse proxy

### Docker Usage

```bash
docker run -p7860:7860 amhma/ubuntu-desktop
```

variables:
- `-p7860:7860` - port forwarding (must match the ENDPOINT_PORT variable, default is 7860)
- `-e DISPLAY=:1` - X11 display (default: :1)
- `-e SCREEN_SIZE=1920x1080x24` - screen resolution and color depth (default: 1920x1080x24)
- `-e SERVER_TYPE=mcp` - server type (default: mcp) values: mcp, fastapi
- `-e DPI=96` - display DPI (default: 96)
- `-e NOVNC_SERVER_ENABLED=true` - enable noVNC server (default: true)
- `-e SESSION_PASSWORD=""` - session password (default: empty)
- `-e ENDPOINT_PORT=7860` - endpoint port (default: 7860)
