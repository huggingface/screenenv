from typing import Literal

from screenenv import get_logger
from screenenv.screen_remote_env import ScreenRemoteEnv, ScreenSize

logger = get_logger(__name__)


class MCPScreenRemoteServer(ScreenRemoteEnv):
    def __init__(
        self,
        os_type: Literal["Ubuntu", "Windows", "MacOS"] = "Ubuntu",
        provider_type: Literal["docker", "aws", "hf_inference_endpoint"] = "docker",
        volumes: list[str] = [],
        headless: bool = True,
        novnc_server: bool = True,
        session_password: str | bool = True,
        screen_size: ScreenSize = "1920x1080",
        disk_size: str = "32G",
        ram_size: str = "4G",
        cpu_cores: str = "4",
        shm_size: str = "4g",
    ):
        server_type: Literal["mcp"] = "mcp"
        super().__init__(
            os_type=os_type,
            provider_type=provider_type,
            volumes=volumes,
            headless=headless,
            screen_size=screen_size,
            disk_size=disk_size,
            ram_size=ram_size,
            cpu_cores=cpu_cores,
            server_type=server_type,
            shm_size=shm_size,
            session_password=session_password,
            novnc_server=novnc_server,
        )

        self.mcp_server_json = {
            "name": "MCP Screen Remote Server",
            "transport": {
                "type": "streamable-http",
                "url": self.base_url,
            },
        }
