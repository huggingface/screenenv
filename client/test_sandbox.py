import time

from client.sandbox import Sandbox


def sleep():
    time.sleep(1)


def test_sandbox_sequence(tmp_path=None):
    s = Sandbox()
    try:
        print("Testing execute_python_command...")
        resp = s.execute_python_command("print('hi')", ["os"])
        print(resp)
        sleep()

        print("Testing execute_command...")
        resp = s.execute_command("echo hello")
        print(resp)
        sleep()

        print("Testing get_terminal_output...")
        resp = s.get_terminal_output()
        print(resp)
        sleep()

        print("Testing get_desktop_screenshot...")
        resp = s.get_desktop_screenshot()
        assert isinstance(resp, bytes)
        sleep()

        print("Testing get_playwright_screenshot...")
        resp = s.get_playwright_screenshot()
        sleep()

        print("Testing screenshot...")
        resp = s.screenshot()
        sleep()

        print("Testing get_vm_platform...")
        resp = s.get_vm_platform()
        print(resp)
        sleep()

        print("Testing get_cursor_position...")
        resp = s.get_cursor_position()
        print(resp)
        sleep()

        print("Testing get_window_size...")
        resp = s.get_window_size("xfce4-terminal")
        print(resp)
        sleep()

        print("Testing get_screen_size...")
        resp = s.get_screen_size()
        print(resp)
        sleep()

        print("Testing get_desktop_path...")
        resp = s.get_desktop_path()
        print(resp)
        sleep()

        print("Testing get_directory_tree...")
        resp = s.get_directory_tree("/home/user")
        print(resp)
        sleep()

        print("Testing start_and_end_recording...")
        tmp_path = "/tmp/video.mp4"
        resp = s.start_recording()
        print(resp)
        time.sleep(2)
        local_path = "test.mp4"
        resp = s.end_recording(local_path)
        print(resp)
        sleep()
        exit()

        print("Testing health...")
        assert s.health()
        sleep()

        print("Testing move_mouse...")
        s.move_mouse(100, 100)
        sleep()

        print("Testing mouse_press_release...")
        s.mouse_press()
        s.mouse_release()
        sleep()

        print("Testing left_right_middle_click...")
        s.left_click()
        s.right_click()
        s.middle_click()
        sleep()

        print("Testing double_click...")
        s.double_click()
        sleep()

        print("Testing write...")
        s.write("test")
        sleep()

        print("Testing press...")
        s.press("Enter")
        sleep()

        print("Testing drag...")
        s.drag((100, 100), (200, 200))
        sleep()

        print("Testing scroll...")
        s.scroll(100, 100)
        sleep()

        print("Testing wait...")
        s.wait(100)
        sleep()

        print("Testing open_chrome...")
        resp = s.open_chrome("https://example.com")
        print(resp)
        sleep()

        print("Testing launch...")
        resp = s.launch("xfce4-terminal")
        print(resp)
        sleep()

        print("Testing open...")
        resp = s.open("https://example.com")
        print(resp)
        sleep()

        print("Testing get_current_window_id...")
        resp = s.get_current_window_id()
        print(resp)
        sleep()

        print("Testing get_window_title...")
        win = s.get_current_window_id()
        if hasattr(win, "window_id") and win.window_id is not None:
            resp = s.get_window_title(win.window_id)
            print(resp)
        else:
            print("No valid window_id returned.")
        sleep()

        print("Testing get_application_windows...")
        resp = s.get_application_windows("xfce4-terminal")
        print(resp)
        sleep()
    finally:
        print("Closing sandbox...")
        # s.close()


if __name__ == "__main__":
    test_sandbox_sequence()
