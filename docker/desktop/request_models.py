from typing import List
from fastapi import UploadFile
from pydantic import BaseModel, Field, model_validator
import shlex

class CommandRequest(BaseModel):
    command: str | list[str] = Field(default=[])
    shell: bool = False

    @model_validator(mode="after")
    def post_init(self):
        if not self.command and self.shell:
            self.command = ""
        elif isinstance(self.command, str) and not self.shell:
            self.command = shlex.split(self.command)

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

class WindowRequest(BaseModel):
    window_name: str
    strict: bool = False
    by_class: bool = False 