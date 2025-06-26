import argparse
import concurrent.futures
import json
import os
import subprocess
import threading
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
from e2bqwen import E2BVisionAgent, get_agent_summary_erase_images
from huggingface_hub import get_token
from PIL import Image

from screenenv import Sandbox

load_dotenv(override=True)
# Environment variables and constants
E2B_API_KEY = os.getenv("E2B_API_KEY")
# Try to get token dynamically, fall back to environment variable
try:
    HUGGINGFACE_API_KEY = get_token()
    if not HUGGINGFACE_API_KEY:
        HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
        if not HUGGINGFACE_API_KEY:
            raise ValueError(
                "No Hugging Face token found. Please login with `huggingface-cli login` or set HUGGINGFACE_API_KEY environment variable"
            )
except ImportError:
    # Fall back if huggingface_hub is old version without get_token
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
WIDTH = 1024
HEIGHT = 768
SANDBOX_TIMEOUT = 600  # 10 minutes

# Thread lock for print statements to avoid garbled output
print_lock = threading.Lock()


def thread_safe_print(*args, **kwargs):
    """Thread-safe print function"""
    with print_lock:
        print(*args, **kwargs)


# Get git hash for folder naming
def get_git_hash():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "nogit"
    except:
        return "nogit"


def create_agent(data_dir, desktop, max_steps: int):
    """Create an agent with the E2B desktop sandbox"""
    model = QwenVLAPIModel(
        model_id="Qwen/Qwen2.5-VL-72B-Instruct",
        hf_token=HUGGINGFACE_API_KEY,
    )
    # model = OpenAIServerModel(
    #     model_id="gpt-4o",
    #     api_key=os.getenv("OPENAI_API_KEY")
    # )
    return E2BVisionAgent(
        model=model,
        data_dir=data_dir,
        desktop=desktop,
        max_steps=max_steps,
        verbosity_level=2,
        # planning_interval=10,
    )


def chat_message_to_json(obj):
    """Custom JSON serializer for ChatMessage and related objects"""
    if hasattr(obj, "__dict__"):
        # Create a copy of the object's __dict__ to avoid modifying the original
        result = obj.__dict__.copy()

        # Remove the 'raw' field which may contain non-serializable data
        if "raw" in result:
            del result["raw"]

        # Process the content or tool_calls if they exist
        if "content" in result and result["content"] is not None:
            if hasattr(result["content"], "__dict__"):
                result["content"] = chat_message_to_json(result["content"])

        if "tool_calls" in result and result["tool_calls"] is not None:
            result["tool_calls"] = [
                chat_message_to_json(tc) for tc in result["tool_calls"]
            ]

        return result
    elif isinstance(obj, (list, tuple)):
        return [chat_message_to_json(item) for item in obj]
    else:
        return obj


def save_final_status(folder, status: str, summary, error_message=None) -> None:
    """Save metadata about the run"""
    metadata_path = os.path.join(folder, "metadata.json")
    with open(metadata_path, "w") as output_file:
        output_file.write(
            json.dumps(
                {"status": status, "summary": summary, "error_message": error_message},
                default=chat_message_to_json,
            )
        )


def run_example_once(example_name, example_text, run_index, example_dir, max_steps):
    """Run a single example once and return the result"""
    run_dir = os.path.join(example_dir, f"run_{run_index}")
    os.makedirs(run_dir, exist_ok=True)

    # Save the example text
    with open(os.path.join(run_dir, "task.txt"), "w") as f:
        f.write(example_text)

    thread_safe_print(f"  Starting run {run_index} for example '{example_name}'")

    # Create a new sandbox for this run
    desktop = None
    try:
        desktop = Sandbox(
            api_key=E2B_API_KEY,
            resolution=(WIDTH, HEIGHT),
            dpi=96,
            timeout=SANDBOX_TIMEOUT,
        )

        # Create and run the agent
        agent = create_agent(data_dir=run_dir, desktop=desktop, max_steps=max_steps)

        screenshot_bytes = desktop.screenshot()
        initial_screenshot = Image.open(BytesIO(screenshot_bytes))
        try:
            agent.run(task=example_text, images=[initial_screenshot])
            summary = get_agent_summary_erase_images(agent)
            save_final_status(run_dir, "completed", summary=summary)
            thread_safe_print(
                f"  ✓ Example '{example_name}' run {run_index} completed successfully"
            )
            result = {"status": "completed", "run_dir": run_dir}
        except Exception as e:
            error_message = f"Error in agent execution: {str(e)}"
            thread_safe_print(
                f"  ✗ Example '{example_name}' run {run_index} failed: {error_message}"
            )
            summary = (
                get_agent_summary_erase_images(agent)
                if hasattr(agent, "memory")
                else None
            )
            save_final_status(
                run_dir, "failed", summary=summary, error_message=error_message
            )
            result = {"status": "failed", "run_dir": run_dir, "error": error_message}
    except Exception as e:
        raise e
        error_message = f"Error setting up sandbox: {str(e)}"
        thread_safe_print(
            f"  ✗ Example '{example_name}' run {run_index} failed: {error_message}"
        )
        save_final_status(run_dir, "failed", summary=None, error_message=error_message)
        result = {"status": "failed", "run_dir": run_dir, "error": error_message}
    finally:
        # Always clean up the sandbox
        if desktop:
            try:
                desktop.kill()
            except:
                pass

    return result


import traceback


def run_example(example_name, example_text, num_runs, example_dir, max_steps):
    """Run a single example multiple times using threads for each run"""
    thread_safe_print(f"\nRunning example '{example_name}': '{example_text[:50]}...'")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_runs) as executor:
        # Submit all runs to the executor
        future_to_run = {
            executor.submit(
                run_example_once, example_name, example_text, j, example_dir, max_steps
            ): j
            for j in range(num_runs)
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_run):
            run_index = future_to_run[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                error_traceback = traceback.format_exc()
                thread_safe_print(
                    f"  ✗ Run {run_index} for '{example_name}' generated an exception:\n{error_traceback}"
                )
                results.append(
                    {"status": "error", "run_index": run_index, "error": str(exc)}
                )

    return results


def run_evaluation(examples, num_runs, output_dir, max_parallel, max_steps):
    """Run each example n times and save the results"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    git_hash = get_git_hash()
    eval_dir = os.path.join(output_dir, f"eval_{timestamp}_{git_hash}")
    os.makedirs(eval_dir, exist_ok=True)

    start_time = datetime.now()

    thread_safe_print(f"Starting evaluation. Results will be saved to: {eval_dir}")
    thread_safe_print(
        f"Will run {len(examples)} examples, {num_runs} times each, with {max_parallel} parallel examples"
    )

    # Save examples to the evaluation directory
    with open(os.path.join(eval_dir, "examples.json"), "w") as f:
        json.dump(examples, f, indent=2)

    all_results = {}

    # Run examples in parallel, but limit the number of parallel examples
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        # Prepare the example directories first
        example_dirs = {}
        for example_name in examples:
            example_dir = os.path.join(eval_dir, f"example_{example_name}")
            os.makedirs(example_dir, exist_ok=True)
            example_dirs[example_name] = example_dir

        # Submit all examples to the executor
        future_to_example = {
            executor.submit(
                run_example,
                example_name,
                example_text,
                num_runs,
                example_dirs[example_name],
                max_steps,
            ): example_name
            for example_name, example_text in examples.items()
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_example):
            example_name = future_to_example[future]
            try:
                results = future.result()
                all_results[example_name] = results

                # Calculate success rate for this example
                success_count = sum(1 for r in results if r["status"] == "completed")
                thread_safe_print(
                    f"Example '{example_name}' complete: {success_count}/{num_runs} successful runs ({success_count / num_runs * 100:.1f}%)"
                )
            except Exception as exc:
                thread_safe_print(
                    f"Example '{example_name}' generated an exception: {exc}"
                )
                all_results[example_name] = [{"status": "error", "error": str(exc)}]

    # Calculate overall results and success rates
    success_counts = {
        example_name: sum(1 for r in results if r["status"] == "completed")
        for example_name, results in all_results.items()
    }

    total_runs = sum(len(results) for results in all_results.values())
    total_successes = sum(success_counts.values())

    # Save summary to evaluation directory
    summary = {
        "total_runs": total_runs,
        "total_successes": total_successes,
        "success_rate": total_successes / total_runs if total_runs > 0 else 0,
        "example_success_rates": {
            example_name: success_counts[example_name] / len(all_results[example_name])
            for example_name in examples
        },
    }

    with open(os.path.join(eval_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    thread_safe_print(f"\nEvaluation complete. Results saved to: {eval_dir}")
    thread_safe_print(
        f"Overall success rate: {summary['success_rate'] * 100:.1f}% ({total_successes}/{total_runs})"
    )
    for example_name in examples:
        success_rate = summary["example_success_rates"][example_name] * 100
        thread_safe_print(f"Example '{example_name}': {success_rate:.1f}% success")

    print("Total duration:", datetime.now() - start_time)

    return eval_dir


def main():
    parser = argparse.ArgumentParser(description="Evaluate computer agent on examples")
    parser.add_argument(
        "--num-runs", type=int, default=3, help="Number of runs per example"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./eval_results",
        help="Output directory for evaluation results",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=2,
        help="Maximum number of examples to run in parallel",
    )
    parser.add_argument(
        "--max-steps", type=int, default=200, help="Maximum number of steps in each run"
    )
    args = parser.parse_args()

    # Examples from the original code
    examples = {
        "puppies": "Find me pictures of cute puppies",
        "gmaps": "Use Google Maps to find the Hugging Face HQ in Paris",
        "wiki": "Go to Wikipedia and find what happend on April 4th",
        "commute": "Find out the travel time by train from Bern to Basel on Google Maps",
        "hf_space": "Go to Hugging Face Spaces and then find the Space flux.1 schnell. Use the space to generate an image of a GPU",
    }

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Run the evaluation
    run_evaluation(
        examples, args.num_runs, args.output_dir, args.max_parallel, args.max_steps
    )


if __name__ == "__main__":
    main()
