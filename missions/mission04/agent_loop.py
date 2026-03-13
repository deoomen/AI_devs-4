import base64
import json
import logging
import re
import httpx
from pathlib import Path
from urllib.parse import urljoin

from config import load_config
from services.OpenRouter import OpenRouterClient
from services.ToolCalling import Tool, ToolCalling

log = logging.getLogger(__name__)

WORK_DIR = Path(__file__).parent / ".workspace"
MAX_ITERATIONS = 10
MODEL = "google/gemini-2.5-pro"

SYSTEM_PROMPT = """
Jesteś pracownikiem w Systemie Przesyłek Konduktorskich (SPK).

Twoim głównym zadaniem jest przygotowywanie deklaracji transportu zgodnie z oczekiwaniami użytkownika.

Pracuj krok po kroku.
"""

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _download_file(url: str) -> dict:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    filename = url.rstrip("/").split("/")[-1].split("?")[0] or "file"
    dest = WORK_DIR / filename

    if dest.exists():
        log.info("Already downloaded: %s", dest)
        return {"path": str(dest), "filename": filename, "skipped": True}

    log.info("Downloading %s -> %s", url, dest)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)

    log.info("Saved %d bytes", dest.stat().st_size)
    return {
        "path": str(dest),
        "filename": filename,
        "size": dest.stat().st_size,
        "content_type": response.headers.get("content-type", "unknown"),
    }


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
_IMAGE_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
    ".tiff": "image/tiff", ".tif": "image/tiff",
}


async def _describe_image(path: Path, llm: "OpenRouterClient") -> dict:
    md_path = path.with_suffix(".md")

    mime = _IMAGE_MIME.get(path.suffix.lower(), "image/jpeg")
    data = base64.standard_b64encode(path.read_bytes()).decode()
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            {"type": "text", "text": "Describe this image in detail. Include all visible text, numbers, diagrams, tables, and any other relevant information."},
        ],
    }]

    description = await llm.vision(messages)
    md_path.write_text(description, encoding="utf-8")
    log.info("Image described and saved to %s", md_path)
    return {"content": description, "source": str(md_path)}


async def _read_file(path: str, llm: "OpenRouterClient") -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    if p.suffix.lower() in _IMAGE_EXTENSIONS:
        md_path = p.with_suffix(".md")
        if md_path.exists():
            log.info("Using cached image description: %s", md_path)
            content = md_path.read_text(encoding="utf-8")
            return {"content": content, "source": str(md_path)}
        return await _describe_image(p, llm)
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > 100_000
        return {"content": content[:100_000], "truncated": truncated}
    except Exception as exc:
        return {"error": str(exc)}


async def _extract_links(path: str, base_url: str = "") -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}

    content = p.read_text(encoding="utf-8", errors="replace")

    # HTML href / src
    html_links = re.findall(r'(?:href|src)=["\']([^"\'#][^"\']*)["\']', content)
    # Bare http(s) URLs
    bare_urls = re.findall(r'https?://[^\s\'"<>)\]]+', content)
    # Markdown [text](url)
    md_links = re.findall(r'\[.*?\]\(([^)#][^)]*)\)', content)

    all_links: list[str] = list(dict.fromkeys(html_links + bare_urls + md_links))

    if base_url:
        resolved = []
        for link in all_links:
            if link.startswith("http"):
                resolved.append(link)
            else:
                resolved.append(urljoin(base_url, link))
        all_links = resolved

    return {"links": all_links, "count": len(all_links)}


async def _list_files() -> dict:
    if not WORK_DIR.exists():
        return {"files": [], "directory": str(WORK_DIR)}
    files = [
        {"name": f.name, "size": f.stat().st_size}
        for f in sorted(WORK_DIR.iterdir())
        if f.is_file()
    ]
    return {"files": files, "directory": str(WORK_DIR)}


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def _build_tool_calling(llm: OpenRouterClient) -> ToolCalling:
    tc = ToolCalling()
    tc.register_tool(Tool(
        name="download_file",
        definition={
            "type": "function",
            "function": {
                "name": "download_file",
                "description": "Download a file from a URL and save it locally. Returns the local path and metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to download"},
                    },
                    "required": ["url"],
                },
            },
        },
        handle=_download_file,
    ))
    tc.register_tool(Tool(
        name="read_file",
        definition={
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read and return the contents of a local file. Images are automatically described using vision AI and the description is cached as a .md file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Local file path to read"},
                    },
                    "required": ["path"],
                },
            },
        },
        handle=lambda path: _read_file(path, llm),
    ))
    # tc.register_tool(Tool(
    #     name="extract_links",
    #     definition={
    #         "type": "function",
    #         "function": {
    #             "name": "extract_links",
    #             "description": (
    #                 "Extract all URLs/links from a local file (HTML, Markdown, or plain text). "
    #                 "Returns a list of found URLs. Optionally resolve relative links with base_url."
    #             ),
    #             "parameters": {
    #                 "type": "object",
    #                 "properties": {
    #                     "path": {"type": "string", "description": "Local file path to scan for links"},
    #                     "base_url": {
    #                         "type": "string",
    #                         "description": "Base URL used to resolve relative links (optional)",
    #                     },
    #                 },
    #                 "required": ["path"],
    #             },
    #         },
    #     },
    #     handle=_extract_links,
    # ))
    tc.register_tool(Tool(
        name="list_files",
        definition={
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List all files that have been downloaded to the work directory.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handle=_list_files,
    ))
    return tc


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class AgentLoop:
    def __init__(self) -> None:
        config = load_config()
        self._llm = OpenRouterClient(api_key=config.openrouter_api_key, default_model=MODEL)
        self._tools = _build_tool_calling(self._llm)

    async def run(self, user_message: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(MAX_ITERATIONS):
            log.info("Agent iteration %d/%d", iteration + 1, MAX_ITERATIONS)
            choice = await self._llm.chat_with_tools(
                messages=messages,
                tools=self._tools.get_definitions(),
            )

            if choice.finish_reason == "tool_calls":
                assistant_msg = choice.message
                messages.append(assistant_msg.model_dump(exclude_unset=True))

                for tool_call in assistant_msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    log.info("  -> %s(%s)", name, args)
                    result = await self._tools.execute_tool(name, args)
                    log.info("     result: %s", result[:300])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
            else:
                answer = choice.message.content or ""
                log.info("Agent finished: %s", answer[:200])
                return answer

        return "Max iterations reached without completing the task."
