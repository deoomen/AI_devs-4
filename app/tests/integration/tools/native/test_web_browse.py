import pytest
import httpx
import respx
from src.tools.native.web_browse import _execute, _extract_forms, _html_to_markdown, _sessions
from bs4 import BeautifulSoup


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset persistent session clients between tests."""
    _sessions.clear()
    yield
    _sessions.clear()


# --- pure function tests ---

class TestExtractForms:
    def test_no_forms_returns_empty(self):
        soup = BeautifulSoup("<p>Hello</p>", "html.parser")
        assert _extract_forms(soup) == ""

    def test_single_form_with_fields(self):
        html = """
        <form action="/login" method="post">
            <input name="username" type="text" value="admin">
            <input name="password" type="password">
            <input name="submit" type="submit" value="Login">
        </form>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_forms(soup)
        assert "POST /login" in result
        assert "`username`" in result
        assert "`password`" in result
        assert "admin" in result    # non-password value shown
        assert "Login" in result    # submit value shown (only password type is hidden)

    def test_multiple_forms(self):
        html = """
        <form action="/search" method="get"><input name="q"></form>
        <form action="/submit" method="post"><input name="data"></form>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_forms(soup)
        assert "GET /search" in result
        assert "POST /submit" in result


class TestHtmlToMarkdown:
    def test_strips_scripts_and_styles(self):
        html = "<html><head><script>alert(1)</script><style>body{}</style></head><body><p>Hello</p></body></html>"
        result = _html_to_markdown(html)
        assert "alert" not in result
        assert "body{}" not in result
        assert "Hello" in result

    def test_converts_headings(self):
        html = "<h1>Title</h1><h2>Subtitle</h2><p>Body</p>"
        result = _html_to_markdown(html)
        assert "# Title" in result
        assert "## Subtitle" in result

    def test_appends_forms(self):
        html = '<body><p>text</p><form action="/go" method="post"><input name="x"></form></body>'
        result = _html_to_markdown(html)
        assert "POST /go" in result

    def test_collapses_blank_lines(self):
        html = "<p>a</p>\n\n\n\n<p>b</p>"
        result = _html_to_markdown(html)
        assert "\n\n\n" not in result


# --- HTTP tests ---

@respx.mock
async def test_get_html_page():
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(
            200,
            text="<html><body><h1>Hello</h1></body></html>",
            headers={"content-type": "text/html"},
        )
    )
    result = await _execute({"url": "https://example.com/page"})
    assert not result.is_error
    assert "HTTP 200" in result.output
    assert "Hello" in result.output
    assert "Markdown" in result.output


@respx.mock
async def test_get_json_response():
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(
            200,
            json={"key": "value"},
            headers={"content-type": "application/json"},
        )
    )
    result = await _execute({"url": "https://api.example.com/data"})
    assert not result.is_error
    assert "JSON" in result.output
    assert '"key"' in result.output


@respx.mock
async def test_post_form_data():
    respx.post("https://example.com/login").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Welcome</body></html>",
            headers={"content-type": "text/html"},
        )
    )
    result = await _execute({
        "method": "POST",
        "url": "https://example.com/login",
        "form": {"username": "admin", "password": "secret"},
    })
    assert not result.is_error
    assert "Welcome" in result.output


@respx.mock
async def test_4xx_returns_error():
    respx.get("https://example.com/missing").mock(
        return_value=httpx.Response(404, text="Not Found", headers={"content-type": "text/plain"})
    )
    result = await _execute({"url": "https://example.com/missing"})
    assert result.is_error
    assert "HTTP 404" in result.output


async def test_missing_url():
    result = await _execute({})
    assert result.is_error
    assert "Missing url" in result.output


async def test_unsupported_method():
    result = await _execute({"url": "https://example.com/", "method": "BREW"})
    assert result.is_error
    assert "Unsupported method" in result.output


@respx.mock
async def test_timeout():
    respx.get("https://example.com/slow").mock(side_effect=httpx.TimeoutException("timed out"))
    result = await _execute({"url": "https://example.com/slow"})
    assert result.is_error
    assert "timed out" in result.output


@respx.mock
async def test_request_error():
    respx.get("https://example.com/down").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = await _execute({"url": "https://example.com/down"})
    assert result.is_error
    assert "Request failed" in result.output
