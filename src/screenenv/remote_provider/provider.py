from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class IPAddr(BaseModel):
    ip_address: str
    host_port: dict[int, int]


class Provider(ABC, BaseModel):
    @property
    @abstractmethod
    def id(self) -> str | None:
        """
        Method to get the provider ID.
        """
        ...

    @abstractmethod
    def start_emulator(self):
        """
        Method to start the emulator.
        """
        ...

    @abstractmethod
    def get_ip_address(self) -> IPAddr:
        """
        Method to get the private IP address of the VM. Private IP means inside the VPC.
        """
        ...

    @abstractmethod
    def save_state(self, snapshot_name: str):
        """
        Method to save the state of the VM.
        """
        ...

    @abstractmethod
    def revert_to_snapshot(self, snapshot_name: str) -> str:
        """
        Method to revert the VM to a given snapshot.
        """
        ...

    @abstractmethod
    def reset(self):
        """
        Method to reset the VM.
        """
        ...

    @abstractmethod
    def stop_emulator(self):
        """
        Method to stop the emulator.
        """
        ...

    class Config:
        arbitrary_types_allowed = True


class FakeProviderConfig(BaseModel):
    PROVIDER_NAME: Literal["fake"] = "fake"


class FakeProvider(Provider):
    @property
    def id(self) -> str | None:
        return None

    def start_emulator(self):
        pass

    def get_ip_address(self) -> IPAddr:
        return IPAddr(ip_address="127.0.0.1", host_port={})

    def save_state(self, snapshot_name: str):
        pass

    def revert_to_snapshot(self, snapshot_name: str):
        pass

    def stop_emulator(self):
        pass
