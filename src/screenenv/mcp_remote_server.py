from typing import Literal

from screenenv import get_logger
from screenenv.remote_screen_env import RemoteScreenEnv, StandardScreenSize

logger = get_logger(__name__)


class MCPRemoteServer(RemoteScreenEnv):
    def __init__(
        self,
        os_type: Literal["Ubuntu", "Windows", "MacOS"] = "Ubuntu",
        provider_type: Literal["docker", "aws", "hf"] = "docker",
        volumes: list[str] = [],
        headless: bool = True,
        session_password: str | bool = True,
        resolution: StandardScreenSize | tuple[int, int] = (1920, 1080),
        disk_size: str = "32G",
        ram_size: str = "4G",
        cpu_cores: str = "4",
        shm_size: str = "4g",
        stream_server: bool = True,
        dpi: int = 96,
        api_key: str | None = None,
        timeout: int = 1000,
    ):
        server_type: Literal["mcp"] = "mcp"
        super().__init__(
            os_type=os_type,
            provider_type=provider_type,
            volumes=volumes,
            headless=headless,
            resolution=resolution,
            disk_size=disk_size,
            ram_size=ram_size,
            cpu_cores=cpu_cores,
            server_type=server_type,
            shm_size=shm_size,
            session_password=session_password,
            stream_server=stream_server,
            dpi=dpi,
            api_key=api_key,
            timeout=timeout,
        )
        self.mcp_server_json = {
            "name": "MCP Screen Remote Server",
            "transport": {
                "type": "streamable-http",
                "url": self.base_url,
            },
        }
