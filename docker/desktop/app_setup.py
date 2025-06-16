
from contextlib import asynccontextmanager
from fastapi import FastAPI
import subprocess
import logging
import signal
import pyautogui
import platform


platform_name: str = platform.system()

def _get_libreoffice_version() -> tuple[int, ...]:
    """Function to get the LibreOffice version as a tuple of integers."""
    result = subprocess.run("libreoffice --version", shell=True, text=True, stdout=subprocess.PIPE)
    version_str = result.stdout.split()[1]  # Assuming version is the second word in the command output
    return tuple(map(int, version_str.split(".")))

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

    # Initialize state
    app.state.logger = logger
    app.state.recording_process = None
    app.state.recording_path = "/tmp/recording.mp4"
    if platform_name == "Linux":
        app.state.libreoffice_version_tuple = _get_libreoffice_version()
    
    # Configure pyautogui
    pyautogui.PAUSE = 0
    pyautogui.DARWIN_CATCH_UP_TIME = 0
    
    yield
    
    # Cleanup
    if app.state.recording_process:
        app.state.recording_process.send_signal(signal.SIGINT)
        app.state.recording_process.wait()

app = FastAPI(lifespan=lifespan)