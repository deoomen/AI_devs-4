import csv
import pytest
from pathlib import Path
from src.tools.native.csv_filter import _apply_filter, _transform_value, _execute


# --- pure function tests (no workspace needed) ---

class TestTransformValue:
    def test_year_extracts_year(self):
        assert _transform_value("2024-03-15", "year") == "2024"

    def test_year_already_just_year(self):
        assert _transform_value("2024", "year") == "2024"

    def test_no_transform_returns_raw(self):
        assert _transform_value("hello", None) == "hello"
        assert _transform_value("2024-01-01", None) == "2024-01-01"


class TestApplyFilter:
    def test_eq(self):
        assert _apply_filter("foo", "eq", "foo") is True
        assert _apply_filter("foo", "eq", "bar") is False

    def test_ne(self):
        assert _apply_filter("foo", "ne", "bar") is True
        assert _apply_filter("foo", "ne", "foo") is False

    def test_contains(self):
        assert _apply_filter("hello world", "contains", "world") is True
        assert _apply_filter("hello world", "contains", "xyz") is False

    def test_not_contains(self):
        assert _apply_filter("hello world", "not_contains", "xyz") is True
        assert _apply_filter("hello world", "not_contains", "world") is False

    def test_regex(self):
        assert _apply_filter("abc123", "regex", r"\d+") is True
        assert _apply_filter("abcdef", "regex", r"\d+") is False

    def test_gt_lt(self):
        assert _apply_filter("10", "gt", 5) is True
        assert _apply_filter("3", "gt", 5) is False
        assert _apply_filter("3", "lt", 5) is True
        assert _apply_filter("10", "lt", 5) is False

    def test_gte_lte(self):
        assert _apply_filter("5", "gte", 5) is True
        assert _apply_filter("5", "lte", 5) is True
        assert _apply_filter("4", "gte", 5) is False
        assert _apply_filter("6", "lte", 5) is False

    def test_gt_non_numeric_returns_false(self):
        assert _apply_filter("abc", "gt", 5) is False

    def test_in(self):
        assert _apply_filter("b", "in", ["a", "b", "c"]) is True
        assert _apply_filter("d", "in", ["a", "b", "c"]) is False

    def test_in_string_split(self):
        assert _apply_filter("b", "in", "a,b,c") is True

    def test_between(self):
        assert _apply_filter("5", "between", [3, 7]) is True
        assert _apply_filter("3", "between", [3, 7]) is True
        assert _apply_filter("7", "between", [3, 7]) is True
        assert _apply_filter("10", "between", [3, 7]) is False

    def test_between_non_numeric(self):
        assert _apply_filter("abc", "between", [1, 10]) is False

    def test_between_bad_args(self):
        assert _apply_filter("5", "between", "not-a-list") is False

    def test_year_transform_with_eq(self):
        assert _apply_filter("2024-03-15", "eq", "2024", transform="year") is True
        assert _apply_filter("2023-12-01", "eq", "2024", transform="year") is False

    def test_unknown_operator_returns_false(self):
        assert _apply_filter("foo", "unknown_op", "foo") is False


# --- integration tests using workspace ---

def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


async def test_inspect_mode_no_filters(workspace: Path):
    _write_csv(
        workspace / "notes" / "data.csv",
        [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}],
        ["name", "age"],
    )

    result = await _execute({"input_path": "notes/data.csv"})

    assert not result.is_error
    assert "Schema for" in result.output
    assert "name, age" in result.output


async def test_filter_eq(workspace: Path):
    _write_csv(
        workspace / "notes" / "people.csv",
        [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}],
        ["name", "age"],
    )

    result = await _execute({
        "input_path": "notes/people.csv",
        "output_path": "notes/out.csv",
        "filters": [{"column": "name", "operator": "eq", "value": "Alice"}],
    })

    assert not result.is_error
    assert "1/" in result.output

    with (workspace / "notes" / "out.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"


async def test_filter_unknown_column(workspace: Path):
    _write_csv(
        workspace / "notes" / "data.csv",
        [{"name": "Alice"}],
        ["name"],
    )

    result = await _execute({
        "input_path": "notes/data.csv",
        "filters": [{"column": "nonexistent", "operator": "eq", "value": "x"}],
    })

    assert result.is_error
    assert "Unknown column" in result.output


async def test_filter_missing_input_path(workspace: Path):
    result = await _execute({})
    assert result.is_error
    assert "Missing input_path" in result.output


async def test_filter_file_not_found(workspace: Path):
    result = await _execute({"input_path": "notes/missing.csv"})
    assert result.is_error
    assert "File not found" in result.output


async def test_filter_column_selection(workspace: Path):
    _write_csv(
        workspace / "notes" / "data.csv",
        [{"a": "1", "b": "2", "c": "3"}],
        ["a", "b", "c"],
    )

    result = await _execute({
        "input_path": "notes/data.csv",
        "output_path": "notes/out.csv",
        "filters": [{"column": "a", "operator": "eq", "value": "1"}],
        "columns": ["a", "c"],
    })

    assert not result.is_error
    with (workspace / "notes" / "out.csv").open() as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["a", "c"]
