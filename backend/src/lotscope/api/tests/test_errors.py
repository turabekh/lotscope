import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lotscope.api.errors import register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    return app


async def test_unhandled_error_returns_500_with_cors_headers() -> None:
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/boom", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 500
    assert resp.json()["error"] == "InternalError"
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_unhandled_error_omits_cors_for_disallowed_origin() -> None:
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/boom", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 500
    assert "access-control-allow-origin" not in resp.headers
