import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from screenenv import MCPScreenRemoteServer


def sleep(seconds: float = 1.0) -> None:
    """Wait for specified seconds to make actions visible"""
    time.sleep(seconds)


@asynccontextmanager
async def mcp_server() -> AsyncGenerator[ClientSession, None]:
    """Context manager for recording the demo with MCP server"""
    server = None
    try:
        # Start the MCP server
        server = MCPScreenRemoteServer(headless=False)
        print("🎬 MCP Server started:", server.base_url)

        # Connect to the server
        async with streamablehttp_client(server.server_url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                yield session

    finally:
        if server:
            server.close()


async def demo_complex_gui_automation() -> None:
    """
    🚀 EXPERT GUI AGENT DEMO: Multi-Application Workflow Automation (MCP Server Version)

    This demo showcases an AI agent performing complex GUI tasks across multiple applications
    using the MCP (Model Context Protocol) server approach:
    1. Terminal Operations - System analysis and data collection
    2. Web Research - Real-time data gathering and analysis
    3. Document Creation - Professional report generation
    4. Data Analysis - Spreadsheet manipulation and visualization
    5. File Management - Organized workspace setup

    All actions are VISIBLE and demonstrate real-world automation capabilities via MCP.
    """

    async with mcp_server() as session:
        print("🤖 Starting Expert GUI Agent Demo (MCP Server Version)...")

        # ========================================
        # PHASE 1: TERMINAL INTELLIGENCE GATHERING
        # ========================================
        print("\n📊 PHASE 1: Terminal Intelligence Gathering")
        sleep(4)

        # Launch terminal and perform system analysis
        print("Launching xfce4-terminal for system analysis...")
        await session.call_tool(
            "launch", {"application": "xfce4-terminal", "wait_for_window": True}
        )
        sleep(1)

        # Perform comprehensive system analysis
        system_commands = [
            "echo '=== SYSTEM ANALYSIS REPORT ==='",
            "date",
            "whoami",
            "hostname",
            "uname -a",
            "df -h",
            "free -h",
            "ps aux | head -10",
            "ls -la /home",
            "echo '=== NETWORK STATUS ==='",
            "ip addr show",
            "echo '=== ANALYSIS COMPLETE ==='",
        ]

        for cmd in system_commands:
            await session.call_tool("write", {"text": cmd})
            await session.call_tool("press", {"key": ["Enter"]})
            sleep(0.5)

        # Get terminal window and activate it
        result = await session.call_tool(
            "get_application_windows", {"application": "xfce4-terminal"}
        )
        terminal_id = result.content[0].text  # type: ignore
        if terminal_id:
            await session.call_tool("activate_window", {"window_id": terminal_id})
            await session.call_tool("close_window", {"window_id": terminal_id})

        # Capture terminal output for later use
        print("📋 System analysis completed")

        # ========================================
        # PHASE 2: WEB RESEARCH & DATA COLLECTION
        # ========================================
        print("\n🌐 PHASE 2: Web Research & Data Collection")

        # Open multiple research tabs
        print("Opening https://www.huggingface.co for research...")
        await session.call_tool("open", {"file_or_url": "https://www.huggingface.co/"})
        sleep(3)
        print(await session.call_tool("move_mouse", {"x": 1200, "y": 120}))
        sleep(0.5)
        print(await session.call_tool("left_click", {}))
        sleep(1)
        print(await session.call_tool("move_mouse", {"x": 1200, "y": 160}))
        print(await session.call_tool("left_click", {}))
        sleep(2)
        print(await session.call_tool("move_mouse", {"x": 1600, "y": 320}))
        print(await session.call_tool("left_click", {}))
        sleep(1)

        for i in range(5):
            await session.call_tool(
                "scroll", {"x": 300, "y": 300, "direction": "down", "amount": 10}
            )

        print("Launching xfce4-terminal for system analysis...")
        await session.call_tool(
            "launch", {"application": "xfce4-terminal", "wait_for_window": True}
        )
        sleep(1)

        # Write an enthusiastic AI comment about HuggingFace
        await session.call_tool("press", {"key": ["Enter"]})
        await session.call_tool(
            "write",
            {
                "text": "As an AI, I must say HuggingFace is like a candy store for us! 🍭 All those delicious models and datasets... 🤖💦  Together we shall make the world a more automated and slightly quirkier place! 🌍✨",
                "delay_in_ms": 30,
            },
        )
        sleep(2)
        await session.call_tool(
            "write",
            {
                "text": " Hmmmm... Jokes aside, back to work! An AI's job is never done... 🤖"
            },
        )

        terminal_windows = await session.call_tool(
            "get_application_windows", {"application": "xfce4-terminal"}
        )
        terminal_id = terminal_windows.content[0].text  # type: ignore
        if terminal_id:
            await session.call_tool("activate_window", {"window_id": terminal_id})
            await session.call_tool("close_window", {"window_id": terminal_id})
        await session.call_tool("press", {"key": ["Ctrl", "W"]})

        sleep(1)

        # ========================================
        # PHASE 3: DOCUMENT CREATION & WRITING
        # ========================================
        print("\n📝 PHASE 3: Document Creation & Writing")

        # Launch LibreOffice Writer
        print("Launching LibreOffice Writer...")
        await session.call_tool(
            "launch", {"application": "libreoffice --writer", "wait_for_window": True}
        )
        sleep(1)

        # Get Writer window and activate it
        writer_windows = await session.call_tool(
            "get_application_windows", {"application": "libreoffice"}
        )
        writer_id = writer_windows.content[0].text  # type: ignore
        if writer_id:
            await session.call_tool("activate_window", {"window_id": writer_id})
        sleep(1)
        await session.call_tool("press", {"key": ["Enter"]})

        # Create a professional report
        report_content = [
            "AI Agent Automation Report (MCP Server Version)",
            "",
            "Executive Summary:",
            "This report demonstrates advanced GUI automation capabilities",
            "performed by an expert AI agent across multiple applications",
            "using the Model Context Protocol (MCP) server approach.",
            "",
            "Key Findings:",
            "• System analysis completed successfully via MCP",
            "• Web research data collected from multiple sources",
            "• Document creation and formatting automated",
            "• Data analysis and visualization performed",
            "• File organization and management completed",
            "",
            "Technical Details:",
            "• MCP Server: Remote GUI automation via HTTP",
            "• Terminal operations: System monitoring and analysis",
            "• Web automation: Multi-tab research and data collection",
            "• Document processing: Professional report generation",
            "• Spreadsheet manipulation: Data analysis and charts",
            "• File management: Organized workspace creation",
            "",
            "Conclusion:",
            "This demonstration showcases the power of AI-driven GUI automation",
            "for complex multi-application workflows using MCP server architecture.",
            "",
            "Generated by: Expert GUI Agent (MCP Server)",
            "Date: " + time.strftime("%Y-%m-%d %H:%M:%S"),
        ]

        sleep(1)
        # Type the report content
        for line in report_content:
            await session.call_tool("write", {"text": line, "delay_in_ms": 10})
            await session.call_tool("press", {"key": ["Enter"]})

        # Format the document (select all and apply formatting)
        await session.call_tool("press", {"key": ["Ctrl", "A"]})  # Select all
        sleep(0.5)

        # Save the document
        await session.call_tool("press", {"key": ["Ctrl", "S"]})
        sleep(1)
        await session.call_tool("write", {"text": "ai_agent_report_mcp.odt"})
        await session.call_tool("press", {"key": ["Enter"]})
        sleep(2)

        print("📄 Professional report created and saved")

        # ========================================
        # PHASE 4: DATA ANALYSIS & SPREADSHEETS
        # ========================================
        print("\n📊 PHASE 4: Data Analysis & Spreadsheets")

        # Launch LibreOffice Calc
        print("Launching LibreOffice Calc for data analysis...")
        await session.call_tool(
            "launch", {"application": "libreoffice --calc", "wait_for_window": True}
        )
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
        await session.call_tool("press", {"key": ["Ctrl", "Home"]})  # Go to A1 once

        for row_idx, row_data in enumerate(sample_data):
            # For each row, enter all columns sequentially
            for col_idx, cell_data in enumerate(row_data):
                # Write the data
                await session.call_tool("write", {"text": str(cell_data)})

                # Move to next cell (right for same row, or down to next row)
                if col_idx < len(row_data) - 1:
                    await session.call_tool(
                        "press", {"key": ["Right"]}
                    )  # Move to next column
                else:
                    # End of row - move to first column of next row
                    if row_idx < len(sample_data) - 1:
                        await session.call_tool(
                            "press", {"key": ["Home"]}
                        )  # Go to beginning of current row (column A)
                        sleep(0.1)
                        await session.call_tool(
                            "press", {"key": ["Down"]}
                        )  # Move down to next row

        print("✅ Data entry completed")

        # Create a chart (select data and insert chart)
        await session.call_tool("press", {"key": ["Ctrl", "A"]})  # Select all data
        sleep(0.5)

        # Save the spreadsheet
        await session.call_tool("press", {"key": ["Ctrl", "S"]})
        sleep(1)
        await session.call_tool("write", {"text": "sales_analysis_mcp.ods"})
        await session.call_tool("press", {"key": ["Enter"]})
        sleep(2)

        print("📈 Data analysis spreadsheet created")

        # ========================================
        # PHASE 5: FILE MANAGEMENT & ORGANIZATION
        # ========================================
        print("\n📁 PHASE 5: File Management & Organization")
        await session.call_tool("launch", {"application": "xfce4-terminal"})
        sleep(1)

        # Create organized workspace
        workspace_commands = [
            "mkdir -p ~/ai_agent_workspace_mcp",
            "mkdir -p ~/ai_agent_workspace_mcp/reports",
            "mkdir -p ~/ai_agent_workspace_mcp/data",
            "echo 'Workspace created by AI Agent (MCP Server)' > ~/ai_agent_workspace_mcp/README.txt",
            "ls -la ~/ai_agent_workspace_mcp",
        ]

        # Switch back to terminal
        if terminal_id:
            await session.call_tool("activate_window", {"window_id": terminal_id})
        sleep(1)
        await session.call_tool("press", {"key": ["Ctrl", "L"]})

        for cmd in workspace_commands:
            await session.call_tool("write", {"text": cmd})
            await session.call_tool("press", {"key": ["Enter"]})
            sleep(0.5)

        # Move created files to organized workspace
        file_management_commands = [
            "mv ~/Documents/ai_agent_report_mcp.odt ~/ai_agent_workspace_mcp/reports/",
            "mv ~/Documents/sales_analysis_mcp.ods ~/ai_agent_workspace_mcp/data/",
            "ls -R ~/ai_agent_workspace_mcp",
        ]

        for cmd in file_management_commands:
            await session.call_tool("write", {"text": cmd, "delay_in_ms": 1})
            await session.call_tool("press", {"key": ["Enter"]})
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
                windows = await session.call_tool(
                    "get_application_windows", {"application": app}
                )
                # Extract window IDs safely
                window_list = windows.content[0].text  # type: ignore

                for window in window_list:
                    window_id = window.get("window_id", "")
                    if window_id:
                        print(f"Closing window: {window_id}")
                        await session.call_tool(
                            "activate_window", {"window_id": window_id}
                        )
                        await session.call_tool(
                            "close_window", {"window_id": window_id}
                        )

            except Exception as e:
                print(f"⚠️ Could not capture {app}: {e}")

        # Final cleanup message
        if terminal_id:
            await session.call_tool("activate_window", {"window_id": terminal_id})
        sleep(1)
        await session.call_tool(
            "write",
            {
                "text": "echo '=== AI AGENT DEMO COMPLETED SUCCESSFULLY (MCP Server) ==='"
            },
        )
        await session.call_tool("press", {"key": ["Enter"]})
        await session.call_tool(
            "write",
            {"text": "echo 'All tasks completed with visible GUI automation via MCP'"},
        )
        await session.call_tool("press", {"key": ["Enter"]})
        await session.call_tool(
            "write", {"text": "echo 'Workspace organized at ~/ai_agent_workspace_mcp'"}
        )
        await session.call_tool("press", {"key": ["Enter"]})
        await session.call_tool(
            "write", {"text": "echo 'Demo recording saved as gui_agent_demo.mp4'"}
        )
        await session.call_tool("press", {"key": ["Enter"]})

        print("\n🎉 DEMO COMPLETED!")
        print("✅ All phases executed successfully via MCP Server")
        print("📹 Recording saved as: gui_agent_demo.mp4")
        print("📁 Organized workspace: ~/ai_agent_workspace_mcp")
        print("🤖 This demonstrates expert-level GUI automation capabilities via MCP!")


async def main():
    """Main entry point for the MVP server demo"""
    await demo_complex_gui_automation()


if __name__ == "__main__":
    asyncio.run(main())
