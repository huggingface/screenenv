# isort: skip_file

import uuid
import webbrowser
from typing import Literal, Optional, Union

from pydantic import BaseModel


from .remote_provider import (
    DockerProviderConfig,
    create_remote_env_provider,
    IPAddr,
    ProviderClient,
    HealthCheckConfig,
)

from screenenv.logger import get_logger

logger = get_logger(__name__)

# Screen size options for desktop environments
StandardScreenSize = Union[
    # Standard Desktop Resolutions
    tuple[Literal[1920], Literal[1080]],  # Full HD (current default)
    tuple[Literal[1366], Literal[768]],  # HD (laptop standard)
    tuple[Literal[2560], Literal[1440]],  # 2K/QHD
    tuple[Literal[3840], Literal[2160]],  # 4K/UHD
    tuple[Literal[1280], Literal[720]],  # HD Ready
    tuple[Literal[1600], Literal[900]],  # HD+
    tuple[Literal[1920], Literal[1200]],  # WUXGA
    tuple[Literal[2560], Literal[1600]],  # WQXGA
    tuple[Literal[3440], Literal[1440]],  # Ultrawide QHD
    tuple[Literal[5120], Literal[1440]],  # Super Ultrawide
    # Mobile/Tablet Resolutions
    tuple[Literal[1024], Literal[768]],  # iPad (portrait)
    tuple[Literal[768], Literal[1024]],  # iPad (landscape)
    tuple[Literal[360], Literal[640]],  # Mobile portrait
    tuple[Literal[640], Literal[360]],  # Mobile landscape
    # Legacy Resolutions
    tuple[Literal[1024], Literal[600]],  # Netbook
    tuple[Literal[800], Literal[600]],  # SVGA
    tuple[Literal[640], Literal[480]],  # VGA
    # Additional Common Resolutions
    tuple[Literal[1440], Literal[900]],  # Custom laptop
    tuple[Literal[1680], Literal[1050]],  # WSXGA+
    tuple[Literal[1920], Literal[1440]],  # Custom 4:3 ratio
    tuple[Literal[2560], Literal[1080]],  # Ultrawide Full HD
    tuple[Literal[3440], Literal[1440]],  # Ultrawide QHD
    tuple[Literal[3840], Literal[1080]],  # Super Ultrawide Full HD
]


class StreamConfig(BaseModel):
    base_url: str
    ip_addr: IPAddr
    endpoint_port: int = 8080
    session_password: str | None = None
    headless: bool = True


class RemoteScreenEnv:
    """Base class for managing Docker remote environments and services"""

    session_password: str  # if True, a random password is generated
    headless: bool
    novnc_server: bool  # if True, VNC server is enabled. If False, VNC server is disabled and headless is set to True
    environment: dict[str, str]
    volumes: list[str]
    provider: ProviderClient
    ip_addr: IPAddr
    base_url: str
    endpoint_port: int
    server_type: Literal["fastapi", "mcp"]
    server_url: str
    chromium_url: str
    novnc_url: Optional[str]

    class StreamServer:
        def __init__(
            self,
            config: StreamConfig | None = None,
        ):
            if config is None:
                self.stream_url = None
                self.session_password = None

            else:
                # Connect to the container's exposed port from the host through nginx
                self.stream_url = f"{config.base_url}/vnc.html?host={config.ip_addr.ip_address}&port={config.ip_addr.host_port[config.endpoint_port]}&autoconnect=true"
                self.session_password = config.session_password
                if config.session_password:
                    self.stream_url += f"&password={config.session_password}"

                if not config.headless:
                    webbrowser.open(self.stream_url)

        def get_auth_key(self) -> str | None:
            """Get the authentication key for the stream"""
            if self.stream_url is None:
                logger.warning(
                    "Stream server is disabled. Enable it by passing stream_server=True to Sandbox(...) or MCPScreenRemoteServer(...)."
                )
                return None
            if self.session_password is None or not self.session_password:
                logger.warning(
                    "Session password is not set. You can directly use the stream URL to connect to the stream server."
                )
                return None
            return self.session_password

        def get_url(self, auth_key: str | None = None) -> str | None:
            """Get the stream URL"""
            if self.stream_url is None:
                logger.warning(
                    "Stream server is disabled. Enable it by passing stream_server=True to Sandbox(...) or MCPScreenRemoteServer(...)."
                )
                return None
            if auth_key is None or not auth_key:
                return self.stream_url
            return f"{self.stream_url}&password={auth_key}"

    def __init__(
        self,
        os_type: Literal["Ubuntu", "Windows", "MacOS"] = "Ubuntu",
        provider_type: Literal["docker", "aws", "hf"] = "docker",
        volumes: list[str] = [],
        headless: bool = True,
        stream_server: bool = True,
        session_password: str | bool = True,
        resolution: StandardScreenSize | tuple[int, int] = (1920, 1080),
        disk_size: str = "32G",
        ram_size: str = "4G",
        cpu_cores: str = "4",
        server_type: Literal["fastapi", "mcp"] = "fastapi",
        shm_size: str = "4g",  # shared memory size
        dpi: int = 96,  # vnc dpi
        api_key: str | None = None,
        timeout: int = 1000,
    ):
        """
        Initialize the remote environment with Docker configuration.

        Args:
            os_type: Operating system type (currently only Ubuntu supported)
            provider_type: Provider type (currently only docker supported)
            volumes: List of volumes to mount
            headless: Whether to run in headless mode
            auto_ssl: Whether to enable SSL for VNC
            screen_size: Screen resolution
            disk_size: Disk size for the environment
            ram_size: RAM size for the environment
            cpu_cores: Number of CPU cores
            server_type: Type of server to run (fastapi, mcp, etc.)
            shm_size: Shared memory size
            ssl_cert_file: Path to custom SSL certificate file (optional)
            ssl_key_file: Path to custom SSL private key file (optional)
        """

        logger.info(
            "Setting up remote environment using Docker - Initial setup may take 5-10 minutes. Please wait..."
        )
        self.server_type = server_type

        # Set default environment variables
        self.environment = {
            "DISK_SIZE": disk_size,
            "RAM_SIZE": ram_size,
            "CPU_CORES": cpu_cores,
            "SCREEN_SIZE": f"{resolution[0]}x{resolution[1]}x24",
            "SERVER_TYPE": server_type,
            "DPI": str(dpi),
        }

        if not stream_server:
            self.environment["NOVNC_SERVER_ENABLED"] = "false"
            if not headless:
                logger.warning(
                    "Headless mode is not supported when noVNC server is disabled. Setting headless to True"
                )
                headless = True
        else:
            self.environment["NOVNC_SERVER_ENABLED"] = "true"

        # Generate session password for authentication
        if session_password:
            self.session_password = (
                uuid.uuid4().hex if session_password is True else session_password
            )
        else:
            self.session_password = ""
            logger.warning(
                "No session password provided, connection will not be authenticated"
            )
        self.environment["SESSION_PASSWORD"] = self.session_password

        self.headless = headless
        self.volumes = volumes

        self.endpoint_port: int = 7860
        self.environment["ENDPOINT_PORT"] = str(self.endpoint_port)

        ports_to_forward: set[int] = {self.endpoint_port}

        # Configure provider based on OS type
        if os_type == "Ubuntu":
            if provider_type == "docker":
                if api_key is not None:
                    logger.warning(
                        "API key provided, but ignored for the Docker provider."
                    )
                healthcheck_config = HealthCheckConfig(
                    endpoint="/health",
                    port=self.endpoint_port,
                    retry_interval=10,
                )
                config = DockerProviderConfig(
                    ports_to_forward=ports_to_forward,
                    image="amhma/ubuntu-desktop:22.04-0.1.0",
                    healthcheck_config=healthcheck_config,
                    volumes=volumes,
                    shm_size=shm_size,
                    environment=self.environment,
                    timeout=timeout,
                    endpoint_port=self.endpoint_port,
                )
            else:
                raise NotImplementedError(
                    f"Provider type {provider_type} not implemented"
                )
        else:
            raise NotImplementedError(f"OS type {os_type} not implemented")

        # Create and start the provider
        self.provider = create_remote_env_provider(config=config)
        try:
            self.provider.start_emulator()
        except (Exception, KeyboardInterrupt) as e:
            logger.error(f"Error starting emulator: {e}")
            self.provider.stop_emulator()
            raise e

        # Get IP address and set up base URL
        self.ip_addr = self.provider.get_ip_address()
        self.base_url = f"http://{self.ip_addr.ip_address}:{self.ip_addr.host_port[self.endpoint_port]}"
        self.websocket_base_url = f"ws://{self.ip_addr.ip_address}:{self.ip_addr.host_port[self.endpoint_port]}"

        self.server_url = (
            f"{self.base_url}/api"
            if self.server_type == "fastapi"
            else f"{self.base_url}/mcp/"
        )
        self.chromium_url = f"{self.base_url}/browser/"

        self.stream = RemoteScreenEnv.StreamServer(
            config=(
                StreamConfig(
                    base_url=self.base_url,
                    ip_addr=self.ip_addr,
                    endpoint_port=self.endpoint_port,
                    session_password=self.session_password,
                    headless=headless,
                )
                if stream_server
                else None
            )
        )

    def get_ip_address(self):
        """Get the IP address and port mappings of the environment"""
        return self.provider.get_ip_address()

    def get_base_url(self) -> str:
        """Get the base URL for API requests"""
        return self.base_url

    def get_session_password(self) -> str:
        """Get the session password for authentication"""
        return self.session_password

    def get_api_url(self) -> str:
        """Get the API URL through nginx"""
        return self.server_url

    def get_novnc_url(self) -> Optional[str]:
        """Get the noVNC URL through nginx (None if noVNC is disabled)"""
        if not self.novnc_server:
            return None
        return self.novnc_url

    def get_browser_url(self) -> str:
        """Get the browser debugging URL through nginx"""
        return self.chromium_url

    def get_provider_id(self) -> str | None:
        """Get the provider ID"""
        return self.provider.id

    def reset(self):
        """Reset the environment"""
        self.provider.reset()

    def close(self) -> None:
        """Close the environment and clean up resources"""
        # Stop the provider
        self.provider.stop_emulator()

    def kill(self) -> None:
        """Kill the environment (alias for close)"""
        self.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
