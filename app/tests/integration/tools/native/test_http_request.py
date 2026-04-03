import httpx
import respx
from src.tools.native.http_request import _execute, _parse_body, _retry_delay


# --- pure function tests ---

class TestParseBody:
    def test_valid_json(self):
        response = httpx.Response(200, json={"key": "value"})
        body_str, parsed = _parse_body(response)
        assert parsed == {"key": "value"}
        assert '"key"' in body_str

    def test_plain_text(self):
        response = httpx.Response(200, text="hello world")
        body_str, parsed = _parse_body(response)
        assert body_str == "hello world"
        assert parsed is None


class TestRetryDelay:
    def test_429_body_retry_after(self):
        response = httpx.Response(429, json={"retry_after": 4})
        assert _retry_delay(response, {"retry_after": 4}) == 5  # +1 safety margin

    def test_429_body_retry_in(self):
        assert _retry_delay(httpx.Response(429), {"retry_in": 9}) == 10

    def test_429_header_fallback(self):
        response = httpx.Response(429, headers={"Retry-After": "3"})
        assert _retry_delay(response, None) == 4

    def test_429_default_backoff(self):
        response = httpx.Response(429)
        assert _retry_delay(response, None) == 5

    def test_503_delay(self):
        assert _retry_delay(httpx.Response(503), None) == 3

    def test_200_no_retry(self):
        assert _retry_delay(httpx.Response(200), None) is None

    def test_400_no_retry(self):
        assert _retry_delay(httpx.Response(400), None) is None


# --- HTTP tests ---

@respx.mock
async def test_get_success():
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )
    result = await _execute({"method": "GET", "url": "https://api.example.com/data"})
    assert not result.is_error
    assert "HTTP 200" in result.output
    assert '"result"' in result.output


@respx.mock
async def test_post_with_body():
    respx.post("https://api.example.com/submit").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    result = await _execute({
        "method": "POST",
        "url": "https://api.example.com/submit",
        "body": {"name": "test"},
    })
    assert not result.is_error
    assert "HTTP 201" in result.output


@respx.mock
async def test_4xx_returns_error():
    respx.get("https://api.example.com/missing").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    result = await _execute({"method": "GET", "url": "https://api.example.com/missing"})
    assert result.is_error
    assert "HTTP 404" in result.output


@respx.mock
async def test_5xx_returns_error():
    respx.get("https://api.example.com/fail").mock(
        return_value=httpx.Response(500, text="Server Error")
    )
    result = await _execute({"method": "GET", "url": "https://api.example.com/fail"})
    assert result.is_error
    assert "HTTP 500" in result.output


async def test_invalid_method():
    result = await _execute({"method": "BREW", "url": "https://api.example.com/"})
    assert result.is_error
    assert "Invalid method" in result.output


async def test_missing_url():
    result = await _execute({"method": "GET"})
    assert result.is_error
    assert "Missing url" in result.output


async def test_invalid_url():
    result = await _execute({"method": "GET", "url": "not-a-url"})
    assert result.is_error
    assert "Invalid URL" in result.output


@respx.mock
async def test_timeout():
    respx.get("https://api.example.com/slow").mock(side_effect=httpx.TimeoutException("timed out"))
    result = await _execute({"method": "GET", "url": "https://api.example.com/slow"})
    assert result.is_error
    assert "timed out" in result.output


@respx.mock
async def test_request_error():
    respx.get("https://api.example.com/err").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = await _execute({"method": "GET", "url": "https://api.example.com/err"})
    assert result.is_error
    assert "Request failed" in result.output


@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.post("https://api.example.com/submit")
    route.side_effect = [
        httpx.Response(429, json={"retry_after": 0}),
        httpx.Response(200, json={"ok": True}),
    ]
    result = await _execute({"method": "POST", "url": "https://api.example.com/submit"})
    assert not result.is_error
    assert "HTTP 200" in result.output
    assert route.call_count == 2


@respx.mock
async def test_retries_on_503_then_succeeds():
    route = respx.get("https://api.example.com/unstable")
    route.side_effect = [
        httpx.Response(503, text="unavailable"),
        httpx.Response(200, text="ok"),
    ]
    result = await _execute({"method": "GET", "url": "https://api.example.com/unstable"})
    assert not result.is_error
    assert route.call_count == 2
