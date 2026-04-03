from unittest.mock import AsyncMock, patch
import httpx
import respx
from src.config import settings
from src.tools.native.aidevs_headquarters import _execute

HQ_VERIFY = f"{settings.aidevs4_headquarters_system_url}/verify"


async def test_missing_task():
    result = await _execute({"answer": "42"})
    assert result.is_error
    assert "Missing task" in result.output


@respx.mock
async def test_post_success():
    respx.post(HQ_VERIFY).mock(
        return_value=httpx.Response(200, json={"code": 0, "message": "OK"})
    )
    result = await _execute({"task": "poligon", "answer": [1, 2, 3]})
    assert not result.is_error
    assert "HTTP 200" in result.output
    assert '"code"' in result.output


@respx.mock
async def test_4xx_returns_error():
    respx.post(HQ_VERIFY).mock(
        return_value=httpx.Response(400, json={"code": -1, "message": "Wrong answer"})
    )
    result = await _execute({"task": "poligon", "answer": "wrong"})
    assert result.is_error
    assert "HTTP 400" in result.output


@respx.mock
async def test_timeout():
    respx.post(HQ_VERIFY).mock(side_effect=httpx.TimeoutException("timed out"))
    result = await _execute({"task": "poligon", "answer": "x"})
    assert result.is_error
    assert "timed out" in result.output


@respx.mock
async def test_request_error():
    respx.post(HQ_VERIFY).mock(side_effect=httpx.ConnectError("refused"))
    result = await _execute({"task": "poligon", "answer": "x"})
    assert result.is_error
    assert "Request failed" in result.output


@respx.mock
async def test_429_retries_and_succeeds():
    route = respx.post(HQ_VERIFY)
    route.side_effect = [
        httpx.Response(429, json={"retry_after": 1}),
        httpx.Response(200, json={"code": 0, "message": "OK"}),
    ]
    with patch("src.tools.native.aidevs_headquarters.asyncio.sleep", new_callable=AsyncMock):
        result = await _execute({"task": "poligon", "answer": "42"})
    assert not result.is_error
    assert "HTTP 200" in result.output
    assert route.call_count == 2


@respx.mock
async def test_custom_endpoint():
    custom_url = f"{settings.aidevs4_headquarters_system_url}/report"
    respx.post(custom_url).mock(
        return_value=httpx.Response(200, json={"code": 0})
    )
    result = await _execute({"endpoint": "/report", "task": "photos", "answer": {"url": "http://x.com"}})
    assert not result.is_error
    assert "HTTP 200" in result.output
