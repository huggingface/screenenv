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
- 🪟 **Window Management**: Launch, activate, resize, and close applications
- 📁 **File Operations**: Upload, download, and file management
- 🐚 **Terminal Access**: Execute commands and capture output
- 🔒 **Secure**: Isolated environment with session-based authentication

## Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd screenenv
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers** (required for web automation):
   ```bash
   playwright install
   ```

4. **Install the package**:
   ```bash
   pip install -e .
   ```

> For usage, see the source code in `examples/sandbox_demo.py`

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
sandbox.scroll(x=500, y=500, direction="down", amount=3)
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
browser_screenshot = sandbox.playwright_screenshot()

# Stop recording and save
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

## System Requirements

- **Docker**: Must be installed and running
- **Python**: 3.8 or higher
- **Playwright**: For web automation features
- **Memory**: At least 4GB RAM recommended
- **Storage**: At least 10GB free space

## Docker Image

The sandbox uses a custom Ubuntu 22.04 Docker image with:
- XFCE4 desktop environment
- VNC server for remote access
- Google Chrome/Chromium browser
- LibreOffice suite
- Python development tools
- Various system utilities

## Troubleshooting

### Common Issues

1. **Docker not running**:
   ```bash
   # Start Docker service
   sudo systemctl start docker
   sudo python3 -m examples.sandbox_demo
   ```

2. **VNC connection issues**:
   - Try disabling SSL with `auto_ssl=False`
