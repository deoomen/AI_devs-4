from unittest.mock import AsyncMock, patch
from src.tools.native.wait import _execute


async def test_wait_sleeps_given_seconds():
    with patch("src.tools.native.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _execute({"seconds": 5})
    assert not result.is_error
    assert "Waited 5 second(s)." == result.output
    mock_sleep.assert_called_once_with(5)


async def test_wait_default_is_3():
    with patch("src.tools.native.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _execute({})
    assert not result.is_error
    assert "Waited 3 second(s)." == result.output
    mock_sleep.assert_called_once_with(3)


async def test_wait_clamps_min_to_1():
    with patch("src.tools.native.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _execute({"seconds": 0})
    assert not result.is_error
    assert "Waited 1 second(s)." == result.output
    mock_sleep.assert_called_once_with(1)


async def test_wait_clamps_max_to_30():
    with patch("src.tools.native.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _execute({"seconds": 999})
    assert not result.is_error
    assert "Waited 30 second(s)." == result.output
    mock_sleep.assert_called_once_with(30)
