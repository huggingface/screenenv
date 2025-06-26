from smolagents.models import Model, ChatMessage, Tool, MessageRole
from time import sleep
from typing import List, Dict, Optional
from huggingface_hub import hf_hub_download
import json


class FakeModelReplayLog(Model):
    """A model class that returns pre-recorded responses from a log file.

    This class is useful for testing and debugging purposes, as it doesn't make
    actual API calls but instead returns responses from a pre-recorded log file.

    Parameters:
        log_url (str, optional):
            URL to the log file. Defaults to the smolagents example log.
        **kwargs: Additional keyword arguments passed to the Model base class.
    """

    def __init__(self, log_folder: str, **kwargs):
        super().__init__(**kwargs)
        self.dataset_name = "smolagents/computer-agent-logs"
        self.log_folder = log_folder
        self.call_counter = 0
        self.model_outputs = self._load_model_outputs()

    def _load_model_outputs(self) -> List[str]:
        """Load model outputs from the log file using HuggingFace datasets library."""
        # Download the file from Hugging Face Hub
        file_path = hf_hub_download(
            repo_id=self.dataset_name,
            filename=self.log_folder + "/metadata.json",
            repo_type="dataset",
        )

        # Load and parse the JSON data
        with open(file_path, "r") as f:
            log_data = json.load(f)

        # Extract only the model_output from each step in tool_calls
        model_outputs = []

        for step in log_data["summary"][1:]:
            model_outputs.append(step["model_output_message"]["content"])

        print(f"Loaded {len(model_outputs)} model outputs from log file")
        return model_outputs

    def __call__(
        self,
        messages: List[Dict[str, str]],
        stop_sequences: Optional[List[str]] = None,
        grammar: Optional[str] = None,
        tools_to_call_from: Optional[List[Tool]] = None,
        **kwargs,
    ) -> ChatMessage:
        """Return the next pre-recorded response from the log file.

        Parameters:
            messages: List of input messages (ignored).
            stop_sequences: Optional list of stop sequences (ignored).
            grammar: Optional grammar specification (ignored).
            tools_to_call_from: Optional list of tools (ignored).
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            ChatMessage: The next pre-recorded response.
        """
        sleep(1.0)

        # Get the next model output
        if self.call_counter < len(self.model_outputs):
            content = self.model_outputs[self.call_counter]
            self.call_counter += 1
        else:
            content = "No more pre-recorded responses available."

        # Token counts are simulated
        self.last_input_token_count = len(str(messages)) // 4  # Rough approximation
        self.last_output_token_count = len(content) // 4  # Rough approximation

        # Create and return a ChatMessage
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=None,
            raw={"source": "pre-recorded log", "call_number": self.call_counter},
        )
