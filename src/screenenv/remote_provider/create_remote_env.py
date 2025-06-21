from typing import Annotated, TypeAlias, overload

from pydantic import Field

from .docker.provider import DockerProvider, DockerProviderConfig
from .provider import FakeProvider, FakeProviderConfig

ProviderConfig: TypeAlias = Annotated[
    DockerProviderConfig | FakeProviderConfig,
    Field(discriminator="PROVIDER_NAME"),
]
ProviderClient: TypeAlias = DockerProvider | FakeProvider


# fmt: off
@overload
def create_remote_env_provider(config: DockerProviderConfig) -> DockerProvider: ...
@overload
def create_remote_env_provider(config: ProviderConfig) -> ProviderClient: ...
# fmt: on
def create_remote_env_provider(config: ProviderConfig) -> ProviderClient:
    if config.PROVIDER_NAME == "docker":
        return DockerProvider(config=config)
    raise NotImplementedError(f"Provider {config.PROVIDER_NAME} not implemented")
