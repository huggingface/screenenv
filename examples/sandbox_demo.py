import time
from contextlib import contextmanager
from typing import Generator

from screenenv import Sandbox


def sleep(seconds: float = 1.0) -> None:
    """Wait for specified seconds to make actions visible"""
    time.sleep(seconds)


@contextmanager
def recording() -> Generator[Sandbox, None, None]:
    """Context manager for recording the demo"""
    try:
        s = Sandbox(headless=False, session_password=True)
        resp = s.start_recording()
        print("🎬 Recording started:", resp)
        yield s
        resp = s.end_recording("gui_agent_demo.mp4")
        print("🎬 Recording saved:", resp)
        sleep()
    finally:
        s.close()


def demo_complex_gui_automation() -> None:
    """
    🚀 EXPERT GUI AGENT DEMO: Multi-Application Workflow Automation

    This demo showcases an AI agent performing complex GUI tasks across multiple applications:
    1. Terminal Operations - System analysis and data collection
    2. Web Research - Real-time data gathering and analysis
    3. Document Creation - Professional report generation
    4. Data Analysis - Spreadsheet manipulation and visualization
    5. File Management - Organized workspace setup

    All actions are VISIBLE and demonstrate real-world automation capabilities.
    """

    with recording() as s:
        # print("🤖 Starting Expert GUI Agent Demo...")

        # # ========================================
        # # PHASE 1: TERMINAL INTELLIGENCE GATHERING
        # # ========================================
        # print("\n📊 PHASE 1: Terminal Intelligence Gathering")
        # sleep(4)

        # # Launch terminal and perform system analysis
        # print("Launching xfce4-terminal for system analysis...")
        # s.launch("xfce4-terminal", wait_for_window=True)
        # sleep(1)

        # # Perform comprehensive system analysis
        # system_commands = [
        #     "echo '=== SYSTEM ANALYSIS REPORT ==='",
        #     "date",
        #     "whoami",
        #     "hostname",
        #     "uname -a",
        #     "df -h",
        #     "free -h",
        #     "ps aux | head -10",
        #     "ls -la /home",
        #     "echo '=== NETWORK STATUS ==='",
        #     "ip addr show",
        #     "echo '=== ANALYSIS COMPLETE ==='",
        # ]

        # for cmd in system_commands:
        #     s.write(cmd, delay_in_ms=10)
        #     s.press("Enter")
        #     sleep(0.5)

        # sleep(0.5)

        # # Get terminal window and activate it
        # terminal_windows = s.get_application_windows("xfce4-terminal")
        # terminal_id = terminal_windows[0]
        # s.activate_window(terminal_id)

        # s.close_window(terminal_id)

        # # Capture terminal output for later use
        # print("📋 System analysis completed")

        # # ========================================
        # # PHASE 2: WEB RESEARCH & DATA COLLECTION
        # # ========================================
        # print("\n🌐 PHASE 2: Web Research & Data Collection")

        # Open multiple research tabs
        # print("Opening https://www.huggingface.co for research...")
        # s.open("https://www.huggingface.co/")
        # sleep(1)
        # s.move_mouse(1200, 120)
        # sleep(0.5)
        # s.left_click()
        # sleep(1)
        # s.move_mouse(1200, 160)
        # s.left_click()
        # sleep(2)
        # s.move_mouse(1600, 320)
        # s.left_click()
        # sleep(1)

        # for i in range(5):
        #     s.scroll(direction="down", amount=10)

        # print("Launching xfce4-terminal for system analysis...")
        # s.launch("xfce4-terminal", wait_for_window=True)
        # sleep(1)

        # # Write an enthusiastic AI comment about HuggingFace
        # s.press("Enter")
        # s.write(
        #     "As an AI, I must say HuggingFace is like a candy store for us! 🍭 All those delicious models and datasets... 🤖💦  Together we shall make the world a more automated and slightly quirkier place! 🌍✨",
        #     delay_in_ms=10,
        # )
        # sleep(2)
        # s.write(
        #     " Hmmmm... Jokes aside, back to work! An AI's job is never done... 🤖",
        #     delay_in_ms=10,
        # )
        # terminal_windows = s.get_application_windows("xfce4-terminal")
        # terminal_id = terminal_windows[0]
        # s.activate_window(terminal_id)
        # s.close_window(terminal_id)
        # s.press(["Ctrl", "W"])

        # sleep(1)

        # ========================================
        # PHASE 3: DOCUMENT CREATION & WRITING
        # ========================================
        print("\n📝 PHASE 3: Document Creation & Writing")

        # Launch LibreOffice Writer
        print("Launching LibreOffice Writer...")
        sleep(2)
        s.launch("libreoffice --writer", wait_for_window=True)
        sleep(1)
        s.press("Enter")

        # Create a professional report
        report_content = [
            "AI Agent Automation Report",
            "",
            "Executive Summary:",
            "This report demonstrates advanced GUI automation capabilities",
            "performed by an expert AI agent across multiple applications.",
            "",
            "Key Findings:",
            "• System analysis completed successfully",
            "• Web research data collected from multiple sources",
            "• Document creation and formatting automated",
            "• Data analysis and visualization performed",
            "• File organization and management completed",
            "",
            "Technical Details:",
            "• Terminal operations: System monitoring and analysis",
            "• Web automation: Multi-tab research and data collection",
            "• Document processing: Professional report generation",
            "• Spreadsheet manipulation: Data analysis and charts",
            "• File management: Organized workspace creation",
            "",
            "Conclusion:",
            "This demonstration showcases the power of AI-driven GUI automation",
            "for complex multi-application workflows in real-world scenarios.",
            "",
            "Generated by: Expert GUI Agent",
            "Date: " + time.strftime("%Y-%m-%d %H:%M:%S"),
        ]

        sleep(1)
        # Type the report content
        for line in report_content:
            s.write(line, delay_in_ms=1)
            s.press("Enter")

        # Format the document (select all and apply formatting)
        s.press(["Ctrl", "A"])  # Select all
        sleep(0.5)

        # Save the document
        s.press(["Ctrl", "S"])
        sleep(1)
        s.write("ai_agent_report.odt")
        s.press("Enter")
        sleep(2)

        print("📄 Professional report created and saved")

        # ========================================
        # PHASE 4: DATA ANALYSIS & SPREADSHEETS
        # ========================================
        print("\n📊 PHASE 4: Data Analysis & Spreadsheets")

        # Launch LibreOffice Calc
        print("Launching LibreOffice Calc for data analysis...")
        s.launch("libreoffice --calc", wait_for_window=True)
        sleep(1)

        # Create sample data for analysis
        sample_data = [
            ["Month", "Sales", "Revenue", "Growth"],
            ["January", "150", "15000", "5%"],
            ["February", "180", "18000", "20%"],
            ["March", "220", "22000", "22%"],
            ["April", "250", "25000", "14%"],
            ["May", "280", "28000", "12%"],
            ["June", "320", "32000", "14%"],
        ]

        # Enter data into spreadsheet - OPTIMIZED VERSION
        print("📊 Entering data into spreadsheet...")

        # Start at A1 and enter data row by row for better efficiency
        s.press(["Ctrl", "Home"])  # Go to A1 once

        for row_idx, row_data in enumerate(sample_data):
            # For each row, enter all columns sequentially
            for col_idx, cell_data in enumerate(row_data):
                # Write the data
                s.write(str(cell_data))

                # Move to next cell (right for same row, or down to next row)
                if col_idx < len(row_data) - 1:
                    s.press("Right")  # Move to next column
                else:
                    # End of row - move to first column of next row
                    if row_idx < len(sample_data) - 1:
                        s.press("Home")  # Go to beginning of current row (column A)
                        sleep(0.1)
                        s.press("Down")  # Move down to next row

        print("✅ Data entry completed")

        # Create a chart (select data and insert chart)
        s.press(["Ctrl", "A"])  # Select all data
        sleep(0.5)

        # Save the spreadsheet
        s.press(["Ctrl", "S"])
        sleep(1)
        s.write("sales_analysis.ods")
        s.press("Enter")
        sleep(2)

        print("📈 Data analysis spreadsheet created")

        print("\n📁 PHASE 5: File Management & Organization")
        s.launch("xfce4-terminal")
        sleep(1)

        # Create organized workspace
        workspace_commands = [
            "mkdir -p ~/ai_agent_workspace",
            "mkdir -p ~/ai_agent_workspace/reports",
            "mkdir -p ~/ai_agent_workspace/data",
            "echo 'Workspace created by AI Agent' > ~/ai_agent_workspace/README.txt",
            "ls -la ~/ai_agent_workspace",
        ]

        # Switch back to terminal
        s.activate_window(terminal_id)
        sleep(1)
        s.press("Ctrl+L")

        for cmd in workspace_commands:
            s.write(cmd, delay_in_ms=10)
            s.press("Enter")
            sleep(0.5)

        # Move created files to organized workspace
        file_management_commands = [
            "mv ~/Documents/ai_agent_report.odt ~/ai_agent_workspace/reports/",
            "mv ~/Documents/sales_analysis.ods ~/ai_agent_workspace/data/",
            "ls -R ~/ai_agent_workspace",
        ]

        for cmd in file_management_commands:
            s.write(cmd, delay_in_ms=1)
            s.press("Enter")
            sleep(0.5)

        print("📂 Workspace organized and files managed")

        # ========================================
        # PHASE 7: FINAL DEMONSTRATION & CLEANUP
        # ========================================
        print("\n🎯 PHASE 7: Final Demonstration & Cleanup")

        # Take final screenshots of all applications
        # Use correct browser name based on architecture
        # x86_64 uses "google-chrome", aarch64 uses "chromium"
        applications = ["chromium", "google-chrome", "libreoffice"]

        for app in applications:
            try:
                windows = s.get_application_windows(app)
                for window in windows:
                    print(f"Closing window: {window}")
                    s.activate_window(window)
                    s.close_window(window)

            except Exception as e:
                print(f"⚠️ Could not capture {app}: {e}")

        # Final cleanup message
        s.activate_window(terminal_id)
        sleep(1)
        s.write("echo '=== AI AGENT DEMO COMPLETED SUCCESSFULLY ==='", delay_in_ms=10)
        s.press("Enter")
        s.write(
            "echo 'All tasks completed with visible GUI automation'", delay_in_ms=10
        )
        s.press("Enter")
        s.write("echo 'Workspace organized at ~/ai_agent_workspace'", delay_in_ms=10)
        s.press("Enter")
        s.write("echo 'Demo recording saved as gui_agent_demo.mp4'", delay_in_ms=10)
        s.press("Enter")

        print("Opening https://www.huggingface.co for research...")
        s.open("https://www.huggingface.co/")
        sleep(1)
        s.move_mouse(1200, 120)
        sleep(0.5)
        s.left_click()
        sleep(1)
        s.move_mouse(1200, 160)
        s.left_click()
        sleep(2)
        s.move_mouse(1600, 320)
        s.left_click()
        sleep(1)

        for i in range(5):
            s.scroll(direction="down", amount=10)

        print("Launching xfce4-terminal for system analysis...")
        s.launch("xfce4-terminal", wait_for_window=True)
        sleep(1)

        # Write an enthusiastic AI comment about HuggingFace
        s.press("Enter")
        s.write(
            "As an AI, I must say HuggingFace is like a candy store for us! 🍭 All those delicious models and datasets... 🤖💦  Together we shall make the world a more automated and slightly quirkier place! 🌍✨",
            delay_in_ms=10,
        )
        sleep(2)
        s.write(
            " Hmmmm... Jokes aside, back to work! An AI's job is never done... 🤖",
            delay_in_ms=10,
        )

        # print("\n🎉 DEMO COMPLETED!")
        # print("✅ All phases executed successfully")
        # print("📹 Recording saved as: gui_agent_demo.mp4")
        # print("📁 Organized workspace: ~/ai_agent_workspace")
        # print("🤖 This demonstrates expert-level GUI automation capabilities!")


if __name__ == "__main__":
    demo_complex_gui_automation()
