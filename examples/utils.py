# Prompt toolkit imports for better interactive input
import os

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style


def get_user_input() -> str | None:
    """Get task input from user using prompt_toolkit for better interaction"""

    # Create history file for command history
    history_file = os.path.expanduser("~/.gui_agent_history")
    history = FileHistory(history_file)

    # Common task examples for auto-completion
    task_examples = [
        "Open LibreOffice, write a report of approximately 5,000 words on the topic ‘AI Agent Workflow in 2025’, and save the document."
    ]

    # Create completer with examples and common words
    completer = WordCompleter(
        task_examples + ["quit", "exit", "help", "clear", "history"],
        ignore_case=True,
    )

    # Create custom key bindings
    kb = KeyBindings()

    @kb.add("f1")
    def _(event):
        """Show help when F1 is pressed"""
        print("\n" + "=" * 60)
        print("🤖 GUI Agent - Desktop Automation Help")
        print("=" * 60)
        print("📝 Enter your task description below.")
        print("Examples:")
        print("  • Open a text editor and type 'Hello World'")
        print("  • Take a screenshot of the desktop")
        print("  • Open calculator and compute 2+2")
        print("  • Open a web browser and navigate to google.com")
        print("\nCommands:")
        print("  • quit/exit - Exit the application")
        print("  • help - Show this help message")
        print("  • clear - Clear the screen")
        print("  • history - Show command history")
        print("\nFeatures:")
        print("  • Tab completion for common tasks")
        print("  • Arrow keys for history navigation")
        print("  • Ctrl+A/Ctrl+E for line navigation")
        print("  • Ctrl+U to clear line")
        print("  • Ctrl+L to clear screen")
        print("-" * 60)

    @kb.add("c-l")
    def _(event):
        """Clear screen when Ctrl+L is pressed"""
        event.app.output.write("\033[2J\033[H")

    # Create custom style
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "input": "ansigreen",
        }
    )

    # Create the prompt session
    session: PromptSession[str] = PromptSession(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=kb,
        style=style,
        enable_history_search=True,
        complete_in_thread=True,
        complete_while_typing=True,
    )

    # Show welcome message
    print("\n" + "=" * 60)
    print("🤖 GUI Agent - Desktop Automation")
    print("=" * 60)
    print("Enter your task description below.")
    print("Examples:")
    print("  • Open a text editor and type 'Hello World'")
    print("  • Take a screenshot of the desktop")
    print("  • Open calculator and compute 2+2")
    print("  • Open a web browser and navigate to google.com")
    print("\nType 'quit' or 'exit' to stop the agent.")
    print("Press F1 for help, Ctrl+L to clear screen")
    print("-" * 60)

    while True:
        try:
            # Create formatted prompt
            prompt_text = FormattedText([("class:prompt", "\n📝 Enter your task: ")])

            task = session.prompt(prompt_text).strip()

            if task.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                return None

            if task.lower() == "help":
                print("\n" + "=" * 60)
                print("🤖 GUI Agent - Desktop Automation Help")
                print("=" * 60)
                print("📝 Enter your task description below.")
                print("Examples:")
                print("  • Open a text editor and type 'Hello World'")
                print("  • Take a screenshot of the desktop")
                print("  • Open calculator and compute 2+2")
                print("  • Open a web browser and navigate to google.com")
                print("\nCommands:")
                print("  • quit/exit - Exit the application")
                print("  • help - Show this help message")
                print("  • clear - Clear the screen")
                print("  • history - Show command history")
                print("\nFeatures:")
                print("  • Tab completion for common tasks")
                print("  • Arrow keys for history navigation")
                print("  • Ctrl+A/Ctrl+E for line navigation")
                print("  • Ctrl+U to clear line")
                print("  • Ctrl+L to clear screen")
                print("-" * 60)
                continue

            if task.lower() == "clear":
                print("\033[2J\033[H")  # Clear screen
                continue

            if task.lower() == "history":
                print("\n📚 Command History:")
                try:
                    history_strings = list(history.load_history_strings())
                    for i, entry in enumerate(history_strings[-10:], 1):
                        print(f"  {i}. {entry}")
                except Exception:
                    print("  No history available yet.")
                continue

            if not task:
                print("❌ Please enter a valid task description.")
                continue

            # Confirm the task with better formatting
            print(f"\n📋 Task: {task}")
            confirm_prompt = FormattedText(
                [("class:prompt", "🚀 Run this task? (y/n): ")]
            )
            confirm = session.prompt(confirm_prompt).strip().lower()

            if confirm in ["y", "yes", ""]:
                return task
            elif confirm in ["n", "no"]:
                print("❌ Task cancelled.")
                continue
            else:
                print("❌ Please enter 'y' for yes or 'n' for no.")
                continue

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            return None
        except EOFError:
            print("\n\n👋 Goodbye!")
            return None
