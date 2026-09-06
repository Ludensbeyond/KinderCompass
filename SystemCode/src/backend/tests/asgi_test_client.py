"""Bounded in-process ASGI client for backend integration tests."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

import httpx
from fastapi import FastAPI


class ASGITestClient:
    """Exercise a FastAPI app with lifespan handling and bounded requests."""

    def __init__(self, app: FastAPI, *, timeout_seconds: float = 5.0) -> None:
        self._app = app
        self._timeout_seconds = timeout_seconds
        self._stack = AsyncExitStack()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ASGITestClient":
        await self._stack.__aenter__()
        await self._stack.enter_async_context(
            self._app.router.lifespan_context(self._app)
        )
        self._client = await self._stack.enter_async_context(
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self._app),
                base_url="http://testserver",
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return await self._stack.__aexit__(exc_type, exc_value, traceback)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("ASGITestClient must be entered before use")
        request = asyncio.create_task(self._client.post(url, **kwargs))
        deadline = asyncio.get_running_loop().time() + self._timeout_seconds
        try:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(
                        f"ASGI request exceeded {self._timeout_seconds:g} seconds"
                    )
                done, _ = await asyncio.wait(
                    {request}, timeout=min(0.05, remaining)
                )
                if done:
                    return request.result()
        finally:
            if not request.done():
                request.cancel()
                try:
                    await request
                except asyncio.CancelledError:
                    pass
