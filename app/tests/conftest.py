from pathlib import Path

# Load test env before any src imports so Settings() picks up test values.
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.test", override=True)

import pytest
from src.tools.workspace import _workspace_root


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Set agent workspace root to a temp directory for the duration of the test.

    Creates the standard subdirs (inbox, notes, outbox) and resets the
    contextvar after the test, regardless of outcome.
    """
    for sub in ("inbox", "notes", "outbox"):
        (tmp_path / sub).mkdir()
    token = _workspace_root.set(tmp_path)
    yield tmp_path
    _workspace_root.reset(token)
