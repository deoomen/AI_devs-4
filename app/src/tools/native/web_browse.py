from loguru import logger

import httpx
from bs4 import BeautifulSoup
import markdownify as md_lib

from src.domain.types import ToolType
from src.runtime.context import get_runtime_context
from ..types import Tool, ToolDefinition, ToolResult

# Persistent session clients keyed by session_id — cookies survive across tool calls
_sessions: dict[str, httpx.AsyncClient] = {}


def _get_or_create_client(session_id: str) -> httpx.AsyncClient:
    if session_id not in _sessions:
        _sessions[session_id] = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        )
        logger.debug("web_browse: created new session client for session={}", session_id)
    return _sessions[session_id]


def _extract_forms(soup: BeautifulSoup) -> str:
    """Extract form metadata (action, method, field names) as a markdown section."""
    forms = soup.find_all("form")
    if not forms:
        return ""

    lines = ["---", "## Forms on this page", ""]
    for form in forms:
        action = form.get("action", "(no action)")
        method = form.get("method", "GET").upper()
        lines.append(f"**Form** `{method} {action}`")
        for inp in form.find_all(["input", "select", "textarea"]):
            name = inp.get("name", "")
            if not name:
                continue
            itype = inp.get("type", "text")
            value = inp.get("value", "")
            entry = f"  - `{name}` (type={itype})"
            if value and itype not in ("password",):
                entry += f" value=`{value}`"
            lines.append(entry)
        lines.append("")

    return "\n".join(lines)


def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Preserve form info before stripping tags
    forms_md = _extract_forms(soup)

    # Remove noise — scripts, styles, non-content elements
    for tag in soup(["script", "style", "meta", "link", "noscript", "head"]):
        tag.decompose()

    # Convert to markdown, strip visual-only tags
    content = md_lib.markdownify(
        str(soup),
        heading_style="ATX",
        strip=["img", "svg", "canvas", "video", "audio"],
    )

    # Collapse excessive blank lines
    import re
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if forms_md:
        content += "\n\n" + forms_md

    return content


async def _execute(arguments: dict) -> ToolResult:
    method = arguments.get("method", "GET").upper()
    url = arguments.get("url", "")
    form = arguments.get("form")
    body = arguments.get("body")
    headers = arguments.get("headers") or {}

    if not url:
        return ToolResult(output="Missing url", is_error=True)
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return ToolResult(output=f"Unsupported method: {method}", is_error=True)

    ctx = get_runtime_context()
    session_id = str(ctx.session_id) if ctx else "default"
    client = _get_or_create_client(session_id)

    logger.debug("web_browse {} {}", method, url)

    req_kwargs: dict = {"method": method, "url": url, "headers": headers}
    if form and method in ("POST", "PUT", "PATCH"):
        req_kwargs["data"] = form          # application/x-www-form-urlencoded
    elif body and method in ("POST", "PUT", "PATCH"):
        req_kwargs["json"] = body          # application/json

    try:
        response = await client.request(**req_kwargs)
    except httpx.TimeoutException:
        return ToolResult(output="Request timed out after 30s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Request failed: {e}", is_error=True)

    content_type = response.headers.get("content-type", "")
    final_url = str(response.url)
    logger.debug("web_browse response: {} url={} content-type={}", response.status_code, final_url, content_type)

    if "text/html" in content_type:
        body_out = _html_to_markdown(response.text)
        label = "Markdown (converted from HTML)"
    elif "application/json" in content_type:
        body_out = response.text
        label = "JSON"
    else:
        body_out = response.text
        label = "Text"

    output = f"HTTP {response.status_code} — {label}\nURL: {final_url}\n\n{body_out}"
    return ToolResult(output=output, is_error=response.status_code >= 400)


web_browse_tool = Tool(
    name="web_browse",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="web_browse",
        description=(
            "Browse web pages using a persistent session — cookies are preserved across calls within the same agent run. "
            "HTML responses are automatically converted to clean Markdown (scripts/styles stripped, forms extracted). "
            "Use for: logging in with a form POST, then navigating authenticated pages with GET. "
            "Session is isolated per agent run (session_id scoped)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method. Default: GET",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to request (e.g. https://example.com/login)",
                },
                "form": {
                    "type": "object",
                    "description": "Form fields for POST — sent as application/x-www-form-urlencoded (use for login forms)",
                },
                "body": {
                    "type": "object",
                    "description": "JSON body for POST — sent as application/json",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional extra HTTP headers as key-value pairs",
                },
            },
            "required": ["url"],
        },
    ),
    execute=_execute,
)
