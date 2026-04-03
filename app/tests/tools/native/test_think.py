import pytest
from src.tools.native.think import _execute


async def test_think_returns_thought():
    result = await _execute({"thought": "hello world"})
    assert not result.is_error
    assert result.output == "hello world"


async def test_think_empty_thought():
    result = await _execute({"thought": ""})
    assert not result.is_error
    assert result.output == ""


async def test_think_missing_key():
    result = await _execute({})
    assert not result.is_error
    assert result.output == ""
