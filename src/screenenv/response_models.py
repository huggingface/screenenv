from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class BaseResponse(BaseModel):
    status: StatusEnum = Field(default=StatusEnum.SUCCESS)
    message: Optional[str] = None


class CommandResponse(BaseResponse):
    output: str = Field(default="")
    error: str = Field(default="")
    returncode: int = Field(default=0)


class DirectoryNode(BaseModel):
    type: str = Field(..., description="Type of the node: 'file' or 'directory'")
    name: str = Field(..., description="Name of the file or directory")
    children: Optional[List["DirectoryNode"]] = Field(
        default=None, description="List of child nodes for directories"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if the node couldn't be accessed"
    )


class DirectoryTreeResponse(BaseResponse):
    path: str = Field(..., description="The root path of the directory tree")
    tree: DirectoryNode = Field(..., description="The directory tree structure")


class ScreenSizeResponse(BaseResponse):
    width: int = Field(..., description="Screen width in pixels")
    height: int = Field(..., description="Screen height in pixels")


class WindowSizeResponse(BaseResponse):
    width: int = Field(..., description="Window width in pixels")
    height: int = Field(..., description="Window height in pixels")
    is_active: bool = Field(..., description="Whether the window is active")
    window_id: str = Field(..., description="Window identifier")
    window_name: Optional[str] = Field(default=None, description="Window title/name")


class DesktopPathResponse(BaseResponse):
    desktop_path: str = Field(..., description="Absolute path to the desktop directory")
    is_writable: bool = Field(
        ..., description="Whether the desktop directory is writable"
    )


class PlatformResponse(BaseResponse):
    platform: str = Field(..., description="Operating system name")
    version: str = Field(..., description="OS version")
    architecture: str = Field(..., description="System architecture")
    machine: str = Field(..., description="Machine type")


class CursorPositionResponse(BaseResponse):
    x: int = Field(..., description="X coordinate of the cursor")
    y: int = Field(..., description="Y coordinate of the cursor")
    screen: int = Field(
        default=0, description="Screen number (for multi-monitor setups)"
    )


class TerminalOutputResponse(BaseResponse):
    output: Optional[str] = Field(default=None, description="Terminal output text")
    exit_code: Optional[int] = Field(
        default=None, description="Exit code of the last command"
    )
    is_active: bool = Field(..., description="Whether the terminal is currently active")


class AccessibilityTreeResponse(BaseResponse):
    at: str = Field(..., description="Accessibility tree in XML format")
    platform: str = Field(
        ..., description="Platform-specific accessibility implementation used"
    )
    timestamp: float = Field(..., description="Timestamp when the tree was generated")


class ErrorResponse(BaseResponse):
    status: StatusEnum = Field(default=StatusEnum.ERROR)
    detail: str = Field(..., description="Detailed error message")
    code: Optional[int] = Field(default=None, description="Error code")
    type: Optional[str] = Field(default=None, description="Error type/classification")


class FileOperationResponse(BaseResponse):
    path: str = Field(..., description="Path of the file that was operated on")
    operation: str = Field(..., description="Type of operation performed")
    size: Optional[int] = Field(default=None, description="File size in bytes")
    mime_type: Optional[str] = Field(default=None, description="MIME type of the file")


class RecordingResponse(BaseResponse):
    path: str = Field(..., description="Path to the recording file")
    size: Optional[int] = Field(
        default=None, description="Size of the recording file in bytes"
    )
    format: str = Field(..., description="Format of the recording (e.g., 'mp4')")


class WindowInfoResponse(BaseResponse):
    window_id: Optional[str] = Field(default=None, description="ID of the window")
    window_name: Optional[str] = Field(default=None, description="Title of the window")


class WindowListResponse(BaseResponse):
    windows: List[WindowInfoResponse] = Field(
        ..., description="List of window information"
    )
