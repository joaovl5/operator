"""File-related toolset."""

from fnmatch import fnmatch
from os import walk
from pathlib import Path as StdPath

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
            _ = await f.write(req.contents)
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
    searched_root: str = Field(description="Directory searched for path matches")
    query_count: int = Field(description="Number of search queries executed")
    match_count: int = Field(description="Number of matching paths returned")


class FileSearchError(ToolError): ...


type FileSearchResponse = FileSearchError | FileSearchSuccess


# TODO: MAKE INJECTABLE CWD DEPENDENCY

CWD_STUB = Path()

_IGNORED_SEARCH_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
    }
)
_GLOB_CHARS = frozenset("*?[")


async def file_search(req: FileSearchRequest) -> FileSearchResponse:
    """Find file paths matching any query string.

    Plain queries are matched as case-insensitive path tokens, so a query like
    ``"openai oauth"`` finds paths containing both words. Queries containing glob
    metacharacters keep glob behavior, for example ``"**/*oauth*.py"``.
    """
    queries: list[str]
    match req.queries:
        case list(x):
            queries = [query.strip() for query in x if query.strip()]
        case str(x):
            queries = [x.strip()] if x.strip() else []
    if not queries:
        return FileSearchError(
            error_code="empty_query",
            error_detail="At least one non-empty query is required for file search",
        )

    try:
        matches: set[str] = set()

        root = StdPath(await CWD_STUB.resolve())
        searchable_paths = list(_iter_search_paths(root=root))
        for query in queries:
            matches.update(_match_paths(query=query, root=root, paths=searchable_paths))

        return FileSearchSuccess(
            files=matches,
            searched_root=str(root),
            query_count=len(queries),
            match_count=len(matches),
        )
    except OSError as error:
        return FileSearchError(error_code="os_error", error_detail=str(error))


def _iter_search_paths(*, root: StdPath) -> list[StdPath]:
    paths: list[StdPath] = []
    for dirpath, dirnames, filenames in walk(root):
        dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in _IGNORED_SEARCH_DIRS)
        current_dir = StdPath(dirpath)
        paths.extend(current_dir / dirname for dirname in dirnames)
        paths.extend(current_dir / filename for filename in sorted(filenames))
    return paths


def _match_paths(*, query: str, root: StdPath, paths: list[StdPath]) -> set[str]:
    if any(char in query for char in _GLOB_CHARS):
        return {
            _relative_path(path=path, root=root)
            for path in paths
            if fnmatch(_relative_path(path=path, root=root), query)
        }

    tokens = [token.casefold() for token in query.split()]
    matches: set[str] = set()
    for path in paths:
        relative_path = _relative_path(path=path, root=root)
        searchable_path = relative_path.casefold()
        if all(token in searchable_path for token in tokens):
            matches.add(relative_path)
    return matches


def _relative_path(*, path: StdPath, root: StdPath) -> str:
    return path.relative_to(root).as_posix()
