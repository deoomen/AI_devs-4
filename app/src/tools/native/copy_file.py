import shutil
from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    src = arguments.get("src", "")
    dest = arguments.get("dest", "")

    if not src:
        return ToolResult(output="Missing src", is_error=True)
    if not dest:
        return ToolResult(output="Missing dest", is_error=True)

    src_path = safe_resolve(src, FileOp.READ)
    if src_path is None:
        return ToolResult(output=f"Read denied: {src}", is_error=True)
    if not src_path.exists():
        return ToolResult(output=f"Source not found: {src}", is_error=True)
    if not src_path.is_file():
        return ToolResult(output=f"Source is not a file: {src}", is_error=True)

    dest_path = safe_resolve(dest, FileOp.WRITE)
    if dest_path is None:
        return ToolResult(output=f"Write denied: {dest} (use notes/, outbox/, or shared/)", is_error=True)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest_path)

    size = dest_path.stat().st_size
    logger.debug("copy_file {} → {} ({} bytes)", src, dest, size)
    return ToolResult(output=f"Copied {src} → {dest} ({size} bytes)")


copy_file_tool = Tool(
    name="copy_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="copy_file",
        description=(
            "Copy a file within the agent workspace without loading its content into context. "
            "Useful for promoting files from inbox/ to shared/ after reviewing sub-agent output, "
            "or for archiving files to a different location. "
            "Source must be readable (inbox/, notes/, outbox/, shared/). "
            "Destination must be writable (notes/, outbox/, shared/). "
            "Creates parent directories automatically. Overwrites destination if it already exists."
        ),
        parameters={
            "type": "object",
            "properties": {
                "src": {
                    "type": "string",
                    "description": "Source file path relative to workspace (e.g. inbox/agnt_abc123/note.md)",
                },
                "dest": {
                    "type": "string",
                    "description": "Destination file path relative to workspace (e.g. shared/kb/miasta/warszawa)",
                },
            },
            "required": ["src", "dest"],
        },
    ),
    execute=_execute,
)
