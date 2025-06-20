from fastapi import UploadFile
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: str | list[str] = Field(default=[])
    timeout: int = 120
    background: bool = False


class WindowSizeRequest(BaseModel):
    app_class_name: str


class DirectoryRequest(BaseModel):
    path: str


class FileRequest(BaseModel):
    file_path: str


class UploadRequest(BaseModel):
    file_path: str
    file_data: UploadFile


class WallpaperRequest(BaseModel):
    path: str


class DownloadRequest(BaseModel):
    url: str
    path: str


class OpenFileRequest(BaseModel):
    path: str
