import csv
import logging
import re

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, get_workspace_root, safe_resolve

logger = logging.getLogger(__name__)


def _transform_value(raw: str, transform: str | None) -> str:
    """Apply an optional transformation to a cell value before comparison."""
    if transform == "year":
        # Extract year from YYYY-MM-DD or similar date string
        parts = raw.split("-")
        return parts[0].strip() if parts else raw
    return raw


def _apply_filter(cell: str, operator: str, filter_value, transform: str | None = None) -> bool:
    """Evaluate a single filter condition against a cell value."""
    value = _transform_value(cell, transform)

    if operator == "eq":
        return value == str(filter_value)
    elif operator == "ne":
        return value != str(filter_value)
    elif operator == "contains":
        return str(filter_value) in value
    elif operator == "not_contains":
        return str(filter_value) not in value
    elif operator == "regex":
        return bool(re.search(str(filter_value), value))
    elif operator in ("gt", "lt", "gte", "lte"):
        try:
            num_val = float(value)
            num_filter = float(filter_value)
        except (ValueError, TypeError):
            return False
        if operator == "gt":
            return num_val > num_filter
        elif operator == "lt":
            return num_val < num_filter
        elif operator == "gte":
            return num_val >= num_filter
        else:  # lte
            return num_val <= num_filter
    elif operator == "in":
        allowed = filter_value if isinstance(filter_value, list) else str(filter_value).split(",")
        return value in [str(v).strip() for v in allowed]
    elif operator == "between":
        if not isinstance(filter_value, list) or len(filter_value) != 2:
            return False
        try:
            num_val = float(value)
            return float(filter_value[0]) <= num_val <= float(filter_value[1])
        except (ValueError, TypeError):
            return False

    return False


async def _execute(arguments: dict) -> ToolResult:
    input_path = arguments.get("input_path", "")
    output_path = arguments.get("output_path")
    filters = arguments.get("filters", [])
    columns = arguments.get("columns")
    preview_rows = arguments.get("preview_rows", 5)

    if not input_path:
        return ToolResult(output="Missing input_path", is_error=True)
    if not filters:
        return ToolResult(output="Missing filters", is_error=True)

    safe_input = safe_resolve(input_path, FileOp.READ)
    if safe_input is None:
        return ToolResult(output=f"Read denied: {input_path} (use inbox/, notes/, or outbox/)", is_error=True)
    if not safe_input.exists():
        return ToolResult(output=f"File not found: {input_path}", is_error=True)

    # Read CSV
    with safe_input.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_columns = list(reader.fieldnames or [])
        rows = list(reader)

    total = len(rows)

    # Apply filters (AND logic — all filters must match)
    filtered = []
    for row in rows:
        match = True
        for flt in filters:
            col = flt.get("column", "")
            op = flt.get("operator", "eq")
            val = flt.get("value")
            transform = flt.get("column_transform")

            cell = row.get(col, "")
            if not _apply_filter(cell, op, val, transform):
                match = False
                break
        if match:
            filtered.append(row)

    # Select columns
    out_columns = [c for c in columns if c in all_columns] if columns else list(all_columns)

    # Determine output path
    if output_path:
        safe_output = safe_resolve(output_path, FileOp.WRITE)
        if safe_output is None:
            return ToolResult(output=f"Write denied: {output_path} (use notes/ or outbox/)", is_error=True)
    else:
        # Default output to notes/ dir (writable) with _filtered suffix
        root = get_workspace_root().resolve()
        default_out = root / "notes" / f"{safe_input.stem}_filtered.csv"
        safe_output = default_out

    safe_output.parent.mkdir(parents=True, exist_ok=True)

    # Write filtered CSV
    with safe_output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filtered)

    # Build preview
    root = get_workspace_root()
    rel_output = safe_output.relative_to(root)

    preview_data = filtered[:preview_rows]
    preview_lines = [",".join(out_columns)]
    for row in preview_data:
        preview_lines.append(",".join(row.get(c, "") for c in out_columns))

    summary = (
        f"Filtered {len(filtered)}/{total} rows → {rel_output}\n"
        f"Columns: {', '.join(out_columns)}\n"
        f"Preview ({min(len(filtered), preview_rows)} rows):\n"
        + "\n".join(preview_lines)
    )

    logger.info("csv_filter: %d/%d rows, saved to %s", len(filtered), total, rel_output)
    return ToolResult(output=summary)


csv_filter_tool = Tool(
    name="csv_filter",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="csv_filter",
        description=(
            "Filter rows in a CSV file by column conditions (AND logic). "
            "Reads from workspace, writes filtered result to workspace. "
            "Returns row count and a preview of matching rows."
        ),
        parameters={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Path to input CSV file relative to workspace",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save filtered CSV (default: {input}_filtered.csv)",
                },
                "filters": {
                    "type": "array",
                    "description": "Filter conditions (all must match — AND logic)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {
                                "type": "string",
                                "description": "Column name to filter on",
                            },
                            "operator": {
                                "type": "string",
                                "enum": [
                                    "eq", "ne",
                                    "contains", "not_contains",
                                    "regex",
                                    "gt", "lt", "gte", "lte",
                                    "in",
                                    "between",
                                ],
                                "description": "Comparison operator",
                            },
                            "value": {
                                "description": (
                                    "Value to compare against. "
                                    "For 'between': [min, max] array. "
                                    "For 'in': array of allowed values."
                                ),
                            },
                            "column_transform": {
                                "type": "string",
                                "enum": ["year"],
                                "description": "Optional transform on column value before comparison (e.g. 'year' extracts year from YYYY-MM-DD date)",
                            },
                        },
                        "required": ["column", "operator", "value"],
                    },
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of columns to include in output (default: all)",
                },
                "preview_rows": {
                    "type": "integer",
                    "description": "Number of preview rows to return (default: 5)",
                },
            },
            "required": ["input_path", "filters"],
        },
    ),
    execute=_execute,
)
