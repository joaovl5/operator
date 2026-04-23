"""File-related toolset."""

from aiofile import async_open
from pydantic import Field, FilePath

from operator_core.toolsets.types import ToolError, ToolSuccess
from operator_shared.forms import BaseForm


class FileReadRequest(BaseForm):
    path: FilePath = Field(description="Path to file to be read")


class FileReadSuccess(ToolSuccess):
    contents: str


class FileReadError(ToolError): ...


type FileReadResponse = FileReadError | FileReadSuccess


async def file_read(req: FileReadRequest) -> FileReadResponse:
    """Reads a file."""
    try:
        async with async_open(req.path, mode="r") as f:
            data: str = await f.read()
            return FileReadSuccess(
                contents=data,
            )
    except OSError as e:
        return FileReadError(
            error_code="os_error",
            error_detail=str(e),
        )


class FileWriteRequest(BaseForm):
    path: FilePath = Field(description="Path to file for writing.")
    contents: str = Field(description="Contents of file to be written.")


class FileWriteSuccess(ToolSuccess): ...


class FileWriteError(ToolError): ...


type FileWriteResponse = FileWriteError | FileWriteSuccess


async def file_write(req: FileWriteRequest) -> FileWriteResponse:
    """Writes a new file.

    Will give an error if attempting to edit/overwrite an existing file, use 'file_edit' instead.
    """
    try:
        async with async_open(req.path, mode="w") as f:
            _ = f.write(req.contents)
            return FileWriteSuccess()
    except OSError as e:
        return FileWriteError(
            error_code="os_error",
            error_detail=str(e),
        )


# impl. hashline later
