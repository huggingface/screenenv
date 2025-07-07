import os
import time
from contextlib import contextmanager
from typing import Generator

from screenenv.sandbox import Sandbox


def sleep(seconds: float = 1.0) -> None:
    time.sleep(1)


@contextmanager
def recording() -> Generator[Sandbox, None, None]:
    try:
        s = Sandbox(headless=False)
        resp = s.start_recording()
        print(resp)
        yield s
        resp = s.end_recording("test.mp4")
        print(resp)
        sleep()
    finally:
        pass
        # s.close()


def test_with_xfce4_terminal() -> None:
    s = Sandbox()
    try:
        print("Testing start_and_end_recording...")
        resp = s.start_recording()
        print(resp)
        sleep()

        print("Launching xfce4-terminal...")
        launch_resp = s.launch("xfce4-terminal")
        print("Launch response:", launch_resp)
        sleep()

        print("Getting current window ID...")
        window_id = s.get_current_window_id()
        print("Current window info:", window_id)
        sleep()

        print("Getting application windows for xfce4-terminal...")
        win_list = s.get_application_windows("xfce4-terminal")
        print("Application windows:", win_list)
        sleep()

        assert win_list[0] == window_id

        print("Getting window title...")
        title_info = s.get_window_title(window_id)
        print("Window title info:", title_info)
        sleep()

        print("Getting window size...")
        size_info = s.window_size(window_id)
        print("Window size info:", size_info)
        sleep()

        print("Activating window...")
        activate_info = s.activate_window(window_id)
        print("Activate window info:", activate_info)
        sleep()

        print("Writing on terminal...")
        s.write("echo hello")
        s.press("Enter")
        sleep()

        print("Getting terminal output...")
        terminal_output = s.get_terminal_output()
        print("Terminal output:", terminal_output)
        sleep()

        print("Getting screen size...")
        screen_size = s.get_screen_size()
        print("Screen size:", screen_size)
        sleep()

        print("Closing window...")
        close_info = s.close_window(window_id)
        print("Close window info:", close_info)
        sleep()

        print("Ending recording...")
        tmp_path = "test0.mp4"
        resp = s.end_recording(tmp_path)
        print("End recording info:", resp)
        sleep()

    finally:
        print("Closing sandbox...")
        s.close()


def test_sandbox_misc_functions() -> None:
    s = Sandbox()
    try:
        print("Testing start_and_end_recording...")
        resp = s.start_recording()
        print(resp)
        sleep()

        print("Testing execute_command...")
        print(s.execute_command("echo test"))
        sleep()

        print("Testing execute_python_command...")
        print(s.execute_python_command("print(123)", ["os"]))
        sleep()

        print("Testing get_accessibility_tree...")
        print(s.get_accessibility_tree())
        sleep()

        print("Testing desktop_path...")
        print(s.desktop_path())
        sleep()

        print("Testing directory_tree...")
        print(s.directory_tree("/tmp"))
        sleep()

        print("Testing upload_file_to_remote ...")
        try:
            s.upload_file_to_remote("README.md", "/tmp/README.md")
            print("Uploaded README.md to /tmp/README.md")
        except Exception as e:
            print("upload_file_to_remote failed:", e)
        sleep()

        print("Testing download_url_file_to_remote ...")
        try:
            s.download_url_file_to_remote(
                "https://www.example.com", "/tmp/example.html"
            )
            print("Downloaded URL to /tmp/example.html")
        except Exception as e:
            print("download_url_file_to_remote failed:", e)
        sleep()

        print("Testing download_file_from_remote (dummy)...")
        try:
            s.download_file_from_remote("/tmp/README.md", "dummy_README.md")
            print("Downloaded /tmp/README.md to dummy_README.md")
            s.download_file_from_remote("/tmp/example.html", "dummy_example.html")
            print("Downloaded /tmp/example.html to dummy_example.html")
        except Exception as e:
            print("download_file_from_remote failed:", e)
        sleep()

        print("Testing open...")
        try:
            print(s.open("https://www.example.com"))
        except Exception as e:
            print("open failed:", e)
        sleep()

        print("Testing desktop_screenshot...")
        try:
            desktop_img = s.desktop_screenshot()
            with open("desktop_screenshot.png", "wb") as f:
                f.write(desktop_img)
        except Exception as e:
            print("desktop_screenshot failed:", e)
        sleep()

        print("Testing playwright_screenshot...")
        try:
            playwright_img = s.playwright_screenshot()
            if playwright_img is not None:
                with open("playwright_screenshot.png", "wb") as f:
                    f.write(playwright_img)
        except Exception as e:
            print("playwright_screenshot failed:", e)
        sleep()

        print("Testing platform...")
        print(s.platform())
        sleep()

        print("Testing wait...")
        s.wait(100)
        print("Waited 100ms")
        sleep()

        print("Testing screenshot...")
        try:
            img = s.screenshot()
            print(f"Screenshot bytes: {len(img) if img else 'None'}")
        except Exception as e:
            print("screenshot failed:", e)
        sleep()

        print("Testing left_click...")
        s.left_click(100, 100)
        print("Left click at (100, 100)")
        sleep()

        print("Testing right_click...")
        s.right_click(100, 100)
        print("Right click at (100, 100)")
        sleep()

        print("Testing middle_click...")
        s.middle_click(100, 100)
        print("Middle click at (100, 100)")
        sleep()

        print("Testing double_click...")
        s.double_click(100, 100)
        print("Double click at (100, 100)")
        sleep()

        print("Testing scroll...")
        s.scroll(direction="down", amount=2)
        print("Scrolled down at (100, 100)")
        sleep()

        print("Testing move_mouse...")
        s.move_mouse(600, 600)
        print("Moved mouse to (600, 600)")
        sleep()

        print("Testing mouse_press...")
        s.mouse_press("left")
        print("Mouse left press")
        sleep()

        print("Testing mouse_release...")
        s.mouse_release("left")
        print("Mouse left release")
        sleep()

        print("Testing get_cursor_position...")
        print(s.get_cursor_position())
        sleep()

        print("Testing write...")
        s.write("test")
        print("Wrote 'test'")
        sleep()

        print("Testing press...")
        s.press("Enter")
        print("Pressed Enter")
        sleep()

        print("Testing drag...")
        s.drag((100, 100), (700, 700))
        print("Dragged from (100, 100) to (700, 700)")
        sleep()

        print("Ending recording...")
        tmp_path = "test1.mp4"
        resp = s.end_recording(tmp_path)
        print("End recording info:", resp)
        sleep()

        print("Testing close...")
        s.close()
        print("Closed sandbox")
        sleep()

        print("Testing kill...")
        s.kill()
        print("Killed sandbox")
        sleep()

    finally:
        try:
            s.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Open in default web browser
    # test_with_xfce4_terminal()
    test_sandbox_misc_functions()
    with recording() as s:
        # URL to your local noVNC tunnel
        # url = "http://localhost:8006/vnc.html?host=localhost&port=8006&autoconnect=true"
        # webbrowser.open(url)
        resp = s.open("https://www.example.com")
        print(resp)
        s.open("https://www.wikipedia.org")

    # remove files created by test
    os.remove("dummy_README.md")
    os.remove("dummy_example.html")
    os.remove("desktop_screenshot.png")
    os.remove("playwright_screenshot.png")
    os.remove("test0.mp4")
    os.remove("test1.mp4")
