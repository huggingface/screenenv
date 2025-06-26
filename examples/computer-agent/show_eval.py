import os
import json
import glob
import traceback
from flask import Flask, render_template, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# Serve the HTML viewer
@app.route("/")
def index():
    return render_template("viewer.html")


# Get list of available evaluations
@app.route("/api/evals")
def list_evals():
    base_dir = request.args.get("path", "./eval_results")
    if not os.path.exists(base_dir):
        return jsonify({"error": f"Path {base_dir} does not exist"}), 404

    eval_dirs = []
    for item in os.listdir(base_dir):
        full_path = os.path.join(base_dir, item)
        if os.path.isdir(full_path) and item.startswith("eval_"):
            eval_dirs.append(item)

    return jsonify(eval_dirs)


# Get examples for an evaluation
@app.route("/api/eval/<eval_id>/examples")
def get_examples(eval_id):
    base_dir = request.args.get("path", "./eval_results")
    eval_path = os.path.join(base_dir, eval_id)

    # Try to read examples.json
    examples_json_path = os.path.join(eval_path, "examples.json")
    examples = {}

    if os.path.exists(examples_json_path):
        try:
            with open(examples_json_path, "r") as f:
                examples = json.load(f)
        except json.JSONDecodeError:
            app.logger.error(f"Error parsing examples.json at {examples_json_path}")

    # If examples.json doesn't exist or is empty, scan for example directories
    if not examples:
        for item in os.listdir(eval_path):
            if os.path.isdir(os.path.join(eval_path, item)) and item.startswith(
                "example_"
            ):
                example_id = item.replace("example_", "")
                example_dir = os.path.join(eval_path, item)

                # Find the first run and read task.txt
                run_dirs = []
                for run_item in os.listdir(example_dir):
                    run_path = os.path.join(example_dir, run_item)
                    if os.path.isdir(run_path) and run_item.startswith("run_"):
                        run_dirs.append(run_item)

                if run_dirs:
                    task_path = os.path.join(example_dir, run_dirs[0], "task.txt")
                    if os.path.exists(task_path):
                        with open(task_path, "r") as f:
                            examples[example_id] = f.read().strip()
                    else:
                        # If no task.txt, try reading from metadata.json
                        metadata_path = os.path.join(
                            example_dir, run_dirs[0], "metadata.json"
                        )
                        if os.path.exists(metadata_path):
                            try:
                                with open(metadata_path, "r") as f:
                                    metadata = json.load(f)
                                    # Look for task in summary[0].task
                                    if (
                                        "summary" in metadata
                                        and metadata["summary"]
                                        and "task" in metadata["summary"][0]
                                    ):
                                        examples[example_id] = metadata["summary"][0][
                                            "task"
                                        ]
                            except:
                                # Default to directory name if all else fails
                                examples[example_id] = f"Task for {example_id}"
                        else:
                            examples[example_id] = f"Task for {example_id}"

    return jsonify(examples)


# Get runs for an example
@app.route("/api/eval/<eval_id>/example/<example_id>/runs")
def get_runs(eval_id, example_id):
    base_dir = request.args.get("path", "./eval_results")
    example_dir = os.path.join(base_dir, eval_id, f"example_{example_id}")

    if not os.path.exists(example_dir):
        return jsonify({"error": f"Example directory not found: {example_dir}"}), 404

    runs = []
    for item in os.listdir(example_dir):
        item_path = os.path.join(example_dir, item)
        if os.path.isdir(item_path) and item.startswith("run_"):
            run_id = item

            # Try to get status from metadata.json
            metadata_path = os.path.join(item_path, "metadata.json")
            status = "unknown"

            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                        status = metadata.get("status", "unknown")
                except Exception as e:
                    app.logger.error(
                        f"Error reading metadata.json for {run_id}: {str(e)}"
                    )

            runs.append({"id": run_id, "status": status})
    app.logger.info(f"runs: {runs}")

    return jsonify(runs)


# Get metadata for a run
@app.route("/api/eval/<eval_id>/example/<example_id>/run/<run_id>/metadata")
def get_metadata(eval_id, example_id, run_id):
    base_dir = request.args.get("path", "./eval_results")
    run_dir = os.path.join(base_dir, eval_id, f"example_{example_id}", run_id)
    metadata_path = os.path.join(run_dir, "metadata.json")
    app.logger.info(f"metadata: {metadata_path}")

    if not os.path.exists(metadata_path):
        return jsonify({"error": "Metadata not found", "path": metadata_path}), 404

    try:
        with open(metadata_path, "r") as f:
            metadata_content = f.read()
            if not metadata_content.strip():
                return jsonify({"error": "Metadata file is empty"}), 404

            metadata = json.loads(metadata_content)
            return jsonify(metadata)
    except json.JSONDecodeError as e:
        error_info = {
            "error": "Invalid JSON in metadata file",
            "details": str(e),
            "path": metadata_path,
        }
        app.logger.error(f"JSON error in {metadata_path}: {str(e)}")
        return jsonify(error_info), 400
    except Exception as e:
        error_info = {
            "error": "Error reading metadata file",
            "details": str(e),
            "traceback": traceback.format_exc(),
            "path": metadata_path,
        }
        app.logger.error(f"Error reading {metadata_path}: {str(e)}")
        return jsonify(error_info), 500


# Get screenshots for a run
@app.route("/api/eval/<eval_id>/example/<example_id>/run/<run_id>/screenshots")
def get_screenshots(eval_id, example_id, run_id):
    base_dir = request.args.get("path", "./eval_results")
    run_dir = os.path.join(base_dir, eval_id, f"example_{example_id}", run_id)

    if not os.path.exists(run_dir):
        return jsonify({"error": f"Run directory not found: {run_dir}"}), 404

    screenshots = []
    for ext in ["png", "jpg", "jpeg"]:
        pattern = os.path.join(run_dir, f"*.{ext}")
        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            screenshots.append(
                {"name": filename, "path": f"/api/image?path={file_path}"}
            )

    # Sort by filename
    screenshots.sort(key=lambda x: x["name"])

    app.logger.info(f"screenshots: {screenshots}")

    return jsonify(screenshots)


# Serve an image file
@app.route("/api/image")
def get_image():
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "No path provided"}), 400

    if not os.path.exists(path):
        return jsonify({"error": f"Image not found at path: {path}"}), 404

    try:
        return send_file(path)
    except Exception as e:
        return jsonify({"error": f"Error serving image: {str(e)}"}), 500


if __name__ == "__main__":
    print("Evaluation Server is running at http://localhost:8000")
    print("Press Ctrl+C to stop the server")

    app.run(debug=True, port=8000)
