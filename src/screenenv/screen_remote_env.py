# isort: skip_file

import os
import uuid
import webbrowser
from typing import Literal, Optional


from .remote_provider import (
    DockerProviderConfig,
    create_remote_env_provider,
    IPAddr,
    ProviderClient,
    HealthCheckConfig,
)

from screenenv.logger import get_logger

logger = get_logger(__name__)

MCP_INIT_REQUEST = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "clientInfo": {"name": "test-client", "version": "1.0"},
        "protocolVersion": "2025-03-26",
        "capabilities": {},
    },
    "id": "init-1",
}

# Screen size options for desktop environments
ScreenSize = Literal[
    # Standard Desktop Resolutions
    "1920x1080",  # Full HD (current default)
    "1366x768",  # HD (laptop standard)
    "2560x1440",  # 2K/QHD
    "3840x2160",  # 4K/UHD
    "1280x720",  # HD Ready
    "1600x900",  # HD+
    "1920x1200",  # WUXGA
    "2560x1600",  # WQXGA
    "3440x1440",  # Ultrawide QHD
    "5120x1440",  # Super Ultrawide
    # Mobile/Tablet Resolutions
    "1024x768",  # iPad (portrait)
    "768x1024",  # iPad (landscape)
    "360x640",  # Mobile portrait
    "640x360",  # Mobile landscape
    # Legacy Resolutions
    "1024x600",  # Netbook
    "800x600",  # SVGA
    "640x480",  # VGA
    # Additional Common Resolutions
    "1440x900",  # Custom laptop
    "1680x1050",  # WSXGA+
    "1920x1440",  # Custom 4:3 ratio
    "2560x1080",  # Ultrawide Full HD
    "3440x1440",  # Ultrawide QHD
    "3840x1080",  # Super Ultrawide Full HD
]


class ScreenRemoteEnv:
    """Base class for managing Docker remote environments and services"""

    session_password: str  # if True, a random password is generated
    headless: bool
    novnc_server: bool  # if True, VNC server is enabled. If False, VNC server is disabled and headless is set to True
    environment: dict[str, str]
    volumes: list[str]
    provider: ProviderClient
    ip_addr: IPAddr
    base_url: str
    server_port: int
    chromium_port: int
    vnc_port: int | None
    vnc_url: str | None

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
        server_type: Literal["fastapi", "mcp"] = "fastapi",
        shm_size: str = "4g",
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

        # Set default environment variables
        self.environment = {
            "DISK_SIZE": disk_size,
            "RAM_SIZE": ram_size,
            "CPU_CORES": cpu_cores,
            "SCREEN_SIZE": f"{screen_size}x24",
            "SERVER_TYPE": server_type,
        }

        if not novnc_server:
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

        self.ssl_cert_file: Optional[str] = None
        self.ssl_key_file: Optional[str] = None
        self.headless = headless
        self.volumes = volumes

        server_port: int = 5000
        vnc_port: int = 8006
        chromium_port: int = 9222

        ports_to_forward = (
            {server_port, vnc_port, chromium_port}
            if novnc_server
            else {server_port, chromium_port}
        )

        # Configure provider based on OS type
        if os_type == "Ubuntu":
            if provider_type == "docker":
                healthcheck_config = HealthCheckConfig(
                    endpoint=("/screenshot" if server_type == "fastapi" else "/mcp/"),
                    port=5000,
                    retry_interval=10,
                    headers=(
                        {"X-Session-Password": self.session_password}
                        if server_type == "fastapi"
                        else {
                            "Accept": "application/json, text/event-stream",
                            "Content-Type": "application/json",
                        }
                    ),
                    json_data=(None if server_type == "fastapi" else MCP_INIT_REQUEST),
                    method=("GET" if server_type == "fastapi" else "POST"),
                )
                config = DockerProviderConfig(
                    ports_to_forward=ports_to_forward,
                    image="huggingface/ubuntu_xfce4:latest",
                    healthcheck_config=healthcheck_config,
                    volumes=volumes,
                    shm_size=shm_size,
                    environment=self.environment,
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
        self.base_url = (
            f"http://{self.ip_addr.ip_address}:{self.ip_addr.host_port[server_port]}"
        )

        # Store port mappings for easy access
        self.server_port = self.ip_addr.host_port[server_port]
        self.chromium_port = self.ip_addr.host_port[chromium_port]
        self.vnc_port = self.ip_addr.host_port[vnc_port] if not headless else None

        if novnc_server:
            # Use HTTPS when SSL is enabled (certificate is handled by noVNC in container)
            vnc_protocol = "http"
            # Connect to the container's exposed port from the host
            self.vnc_url = f"{vnc_protocol}://{self.ip_addr.ip_address}:{self.vnc_port}/vnc.html?host={self.ip_addr.ip_address}&port={self.vnc_port}&autoconnect=true"
            if self.session_password:
                self.vnc_url += f"&password={self.session_password}"

            if not headless:
                webbrowser.open(self.vnc_url)

    def get_ip_address(self):
        """Get the IP address and port mappings of the environment"""
        return self.provider.get_ip_address()

    def get_base_url(self) -> str:
        """Get the base URL for API requests"""
        return self.base_url

    def get_session_password(self) -> str:
        """Get the session password for authentication"""
        return self.session_password

    def get_chromium_port(self) -> int:
        """Get the Chromium debugging port"""
        return self.chromium_port

    def get_vnc_port(self) -> Optional[int]:
        """Get the VNC port (None if headless)"""
        return self.vnc_port

    def get_vnc_url(self) -> Optional[str]:
        """Get the VNC URL (None if headless)"""
        return getattr(self, "vnc_url", None)

    def reset(self):
        """Reset the environment"""
        self.provider.reset()

    def close(self) -> None:
        """Close the environment and clean up resources"""
        # Clean up SSL certificate and key if they exist
        if (
            hasattr(self, "ssl_cert_file")
            and self.ssl_cert_file
            and os.path.exists(self.ssl_cert_file)
        ):
            try:
                os.unlink(self.ssl_cert_file)
                logger.info(f"Cleaned up SSL certificate: {self.ssl_cert_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up SSL certificate: {e}")

        if (
            hasattr(self, "ssl_key_file")
            and self.ssl_key_file
            and os.path.exists(self.ssl_key_file)
        ):
            try:
                os.unlink(self.ssl_key_file)
                logger.info(f"Cleaned up SSL key: {self.ssl_key_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up SSL key: {e}")

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
