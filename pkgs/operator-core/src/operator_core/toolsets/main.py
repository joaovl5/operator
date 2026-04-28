"""File-related toolset."""

from asyncio import Task, create_task, gather

from anyio import Path
from pydantic import Field

from operator_core.toolsets.types import ToolError, ToolSuccess
from operator_shared.forms import BaseForm


class FileReadRequest(BaseForm):
    path: str = Field(description="Path to file to be read")


class FileReadSuccess(ToolSuccess):
    contents: str


class FileReadError(ToolError): ...


type FileReadResponse = FileReadError | FileReadSuccess


async def file_read(req: FileReadRequest) -> FileReadResponse:
    """Reads a file."""
    try:
        path = Path(req.path)
        if not await path.exists():
            return FileReadError(
                error_code="file_missing",
                error_detail="Specified path doesn't exist",
            )
        if not await path.is_file():
            return FileReadError(
                error_code="not_file", error_detail="Specified path doesn't belong to a file"
            )
        async with await path.open(mode="r") as f:
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
    path: str = Field(description="Path to file for writing.")
    contents: str = Field(description="Contents of file to be written.")


class FileWriteSuccess(ToolSuccess): ...


class FileWriteError(ToolError): ...


type FileWriteResponse = FileWriteError | FileWriteSuccess


async def file_write(req: FileWriteRequest) -> FileWriteResponse:
    """Writes a new file.

    Will give an error if attempting to edit/overwrite an existing file, use 'file_edit' instead.
    """
    try:
        path = Path(req.path)
        if await path.exists():
            if not await path.is_file():
                return FileWriteError(
                    error_code="not_file",
                    error_detail="Specified path already exists and does not belong to a file.",
                )
            async with await path.open(mode="r") as f:
                content_len = len(await f.read())
            if content_len > 0:  # edge case of empty files being allowed
                return FileWriteError(
                    error_code="file_exists",
                    error_detail="Cannot use this tool for writing into an already-existing file!",
                )

        async with await path.open(mode="w") as f:
            _ = f.write(req.contents)
            return FileWriteSuccess()
    except OSError as e:
        return FileWriteError(
            error_code="os_error",
            error_detail=str(e),
        )


class FileSearchRequest(BaseForm):
    queries: list[str] | str = Field(
        description="Either a search query or a list of search queries to be made",
    )


class FileSearchSuccess(ToolSuccess):
    files: set[str] = Field(description="Paths of files matching search queries")


class FileSearchError(ToolError): ...


type FileSearchResponse = FileSearchError | FileSearchSuccess


# TODO: MAKE INJECTABLE CWD DEPENDENCY

CWD_STUB = Path()


async def file_search(req: FileSearchRequest) -> FileSearchResponse:
    """Find file paths matching any query string."""
    queries: list[str]
    match req.queries:
        case list(x):
            queries = x
        case str(x):
            queries = [x]
    if not queries:
        return FileSearchError(
            error_code="empty_query",
            error_detail="At least one non-empty query is required for file search",
        )

    try:
        matches: set[str] = set()

        async def _fetch_path_matches(query: str) -> set[str]:
            partial_set: set[str] = set()
            async for match in CWD_STUB.rglob(pattern=query):
                partial_set.add(str(match))
            return partial_set

        match_tasks: list[Task[set[str]]] = [
            create_task(
                _fetch_path_matches(q),
            )
            for q in queries
        ]
        _ = await gather(*match_tasks)
        for match_task in match_tasks:
            matches.update(match_task.result())

        return FileSearchSuccess(files=matches)
    except OSError as error:
        return FileSearchError(error_code="os_error", error_detail=str(error))
