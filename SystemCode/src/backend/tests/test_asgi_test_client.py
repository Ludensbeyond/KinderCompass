import asyncio
import unittest
from contextlib import asynccontextmanager

from fastapi import FastAPI

from SystemCode.src.backend.tests.asgi_test_client import ASGITestClient


class ASGITestClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_runs_application_lifespan(self) -> None:
        events: list[str] = []

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            events.append("startup")
            yield
            events.append("shutdown")

        app = FastAPI(lifespan=lifespan)

        @app.post("/ready")
        async def ready() -> dict[str, bool]:
            return {"ready": True}

        async with ASGITestClient(app) as client:
            response = await client.post("/ready")
            self.assertEqual(events, ["startup"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(events, ["startup", "shutdown"])

    async def test_client_fails_a_stalled_request_within_bound(self) -> None:
        app = FastAPI()
        never = asyncio.Event()

        @app.post("/stalled")
        async def stalled() -> None:
            await never.wait()

        async with ASGITestClient(app, timeout_seconds=0.05) as client:
            with self.assertRaisesRegex(TimeoutError, "exceeded 0.05 seconds"):
                await client.post("/stalled")


if __name__ == "__main__":
    unittest.main()
