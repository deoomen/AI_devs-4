from unittest.mock import AsyncMock, patch
import httpx
import respx
from src.tools.native.zmail import _execute, ZMAIL_URL


async def test_missing_action():
    result = await _execute({})
    assert result.is_error
    assert "Missing action" in result.output


@respx.mock
async def test_post_success():
    respx.post(ZMAIL_URL).mock(
        return_value=httpx.Response(200, json={"emails": [], "total": 0})
    )
    result = await _execute({"action": "getInbox"})
    assert not result.is_error
    assert "HTTP 200" in result.output


@respx.mock
async def test_post_with_params():
    respx.post(ZMAIL_URL).mock(
        return_value=httpx.Response(200, json={"emails": [{"id": 1}]})
    )
    result = await _execute({"action": "getInbox", "params": {"page": 1}})
    assert not result.is_error
    assert '"emails"' in result.output


@respx.mock
async def test_4xx_returns_error():
    respx.post(ZMAIL_URL).mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    result = await _execute({"action": "getInbox"})
    assert result.is_error
    assert "HTTP 401" in result.output


@respx.mock
async def test_timeout():
    respx.post(ZMAIL_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    result = await _execute({"action": "getInbox"})
    assert result.is_error
    assert "timed out" in result.output


@respx.mock
async def test_request_error():
    respx.post(ZMAIL_URL).mock(side_effect=httpx.ConnectError("refused"))
    result = await _execute({"action": "getInbox"})
    assert result.is_error
    assert "Request failed" in result.output


@respx.mock
async def test_429_retries_and_succeeds():
    route = respx.post(ZMAIL_URL)
    route.side_effect = [
        httpx.Response(429, json={"retry_after": 1}),
        httpx.Response(200, json={"emails": []}),
    ]
    with patch("src.tools.native.zmail.asyncio.sleep", new_callable=AsyncMock):
        result = await _execute({"action": "getInbox"})
    assert not result.is_error
    assert route.call_count == 2
