"""
    interface for hardware
"""
from abc import abstractmethod, ABC
from typing import Any


class IHardware(ABC):
    def __init__(self, name: str, address: str):
        self.name: str = name
        self.address: str = address
        self.connected: bool = False

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def configure(self, config: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def control(self, settings: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def write_data(self, data: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def read_data(self, read_buffer: dict[str, Any]) -> bool:
        pass
