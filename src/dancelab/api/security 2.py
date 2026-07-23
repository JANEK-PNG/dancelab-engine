"""Local API trust boundary: path policy and bounded heavy jobs.

The desktop application uses native file pickers and does not pass through this
module. The HTTP API is intentionally narrower: callers may only operate inside
server-configured roots.
"""

from __future__ import annotations

import os
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dancelab.core.config import EngineConfig

DEFAULT_MAX_FILE_BYTES = 2 * 1024**3
DEFAULT_MAX_BATCH_TRACKS = 2_000
DEFAULT_MAX_STEM_TRACKS = 32
DEFAULT_MAX_REQUEST_BYTES = 1024**2
DEFAULT_MAX_CONCURRENT_HEAVY_JOBS = 1


class RequestBodyLimitMiddleware:
    """Reject oversized bodies even when no Content-Length is supplied."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = ApiResourceLimits.from_environment().max_request_bytes
        headers = dict(scope.get("headers", []))
        declared_length = headers.get(b"content-length")
        if declared_length is not None:
            try:
                body_bytes = int(declared_length)
            except (TypeError, ValueError):
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    error="invalid_request",
                    detail="invalid Content-Length",
                )
                return
            if body_bytes < 0:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    error="invalid_request",
                    detail="invalid Content-Length",
                )
                return
            if body_bytes > limit:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    error="request_too_large",
                    detail="request body exceeds API limit",
                )
                return

        messages: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            received_bytes += len(message.get("body", b""))
            if received_bytes > limit:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    error="request_too_large",
                    detail="request body exceeds API limit",
                )
                return
            if not message.get("more_body", False):
                break

        message_index = 0

        async def replay_receive() -> Message:
            nonlocal message_index
            if message_index < len(messages):
                message = messages[message_index]
                message_index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        error: str,
        detail: str,
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content={"error": error, "detail": detail},
        )
        await response(scope, receive, send)


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
    return value


def _configured_roots(name: str, defaults: list[str | Path]) -> tuple[Path, ...]:
    raw = os.environ.get(name)
    values = raw.split(os.pathsep) if raw else [str(value) for value in defaults]
    roots = tuple(Path(value).expanduser().resolve(strict=False) for value in values if value)
    if not roots:
        raise RuntimeError(f"{name} must contain at least one filesystem root")
    return roots


def _is_within(candidate: Path, roots: tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        return True
    return False


@dataclass(frozen=True)
class ApiResourceLimits:
    max_file_bytes: int
    max_batch_tracks: int
    max_stem_tracks: int
    max_request_bytes: int
    max_concurrent_heavy_jobs: int

    @classmethod
    def from_environment(cls) -> "ApiResourceLimits":
        return cls(
            max_file_bytes=_positive_int("DANCELAB_API_MAX_FILE_BYTES", DEFAULT_MAX_FILE_BYTES),
            max_batch_tracks=_positive_int(
                "DANCELAB_API_MAX_BATCH_TRACKS", DEFAULT_MAX_BATCH_TRACKS
            ),
            max_stem_tracks=_positive_int(
                "DANCELAB_API_MAX_STEM_TRACKS", DEFAULT_MAX_STEM_TRACKS
            ),
            max_request_bytes=_positive_int(
                "DANCELAB_API_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES
            ),
            max_concurrent_heavy_jobs=_positive_int(
                "DANCELAB_API_MAX_CONCURRENT_HEAVY_JOBS",
                DEFAULT_MAX_CONCURRENT_HEAVY_JOBS,
            ),
        )


@dataclass(frozen=True)
class ApiPathPolicy:
    input_roots: tuple[Path, ...]
    output_roots: tuple[Path, ...]
    limits: ApiResourceLimits

    @classmethod
    def from_config(cls, config: EngineConfig) -> "ApiPathPolicy":
        processed_dir = os.environ.get(
            "DANCELAB_PROCESSED_DIR", config.paths.processed_dir
        )
        return cls(
            input_roots=_configured_roots(
                "DANCELAB_API_INPUT_ROOTS",
                [config.paths.raw_dir, config.paths.examples_dir],
            ),
            output_roots=_configured_roots(
                "DANCELAB_API_OUTPUT_ROOTS",
                [config.paths.data_dir, processed_dir],
            ),
            limits=ApiResourceLimits.from_environment(),
        )

    def input_file(self, value: str | Path) -> Path:
        source = Path(value).expanduser()
        try:
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail="input file does not exist") from exc
        if not _is_within(resolved, self.input_roots):
            raise HTTPException(status_code=403, detail="input path is outside allowed roots")
        if source.is_symlink() or not resolved.is_file():
            raise HTTPException(status_code=422, detail="input must be a regular file")
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise HTTPException(status_code=422, detail="input file is not readable") from exc
        if size > self.limits.max_file_bytes:
            raise HTTPException(status_code=413, detail="input file exceeds API size limit")
        return resolved

    def input_directory(self, value: str | Path) -> Path:
        source = Path(value).expanduser()
        try:
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail="input directory does not exist") from exc
        if not _is_within(resolved, self.input_roots):
            raise HTTPException(status_code=403, detail="input path is outside allowed roots")
        if source.is_symlink() or not resolved.is_dir():
            raise HTTPException(status_code=422, detail="input must be a directory")
        return resolved

    def output_path(self, value: str | Path) -> Path:
        target = Path(value).expanduser().resolve(strict=False)
        if not _is_within(target, self.output_roots):
            raise HTTPException(status_code=403, detail="output path is outside allowed roots")
        return target

    def validate_audio_tree(self, directory: Path, *, recursive: bool) -> None:
        from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS

        iterator = directory.rglob("*") if recursive else directory.glob("*")
        count = 0
        for path in iterator:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            self.input_file(path)
            count += 1
            if count > self.limits.max_batch_tracks:
                raise HTTPException(
                    status_code=413,
                    detail="audio folder exceeds API track-count limit",
                )


_LIMITS = ApiResourceLimits.from_environment()
_HEAVY_JOB_SEMAPHORE = threading.BoundedSemaphore(
    _LIMITS.max_concurrent_heavy_jobs
)


async def heavy_job_slot() -> AsyncIterator[None]:
    """Reject excess expensive work instead of queueing unbounded requests."""
    if not _HEAVY_JOB_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="another heavy job is already running")
    try:
        yield
    finally:
        _HEAVY_JOB_SEMAPHORE.release()
