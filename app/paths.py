"""Filesystem paths that behave correctly both in development and when the app
is packaged into a standalone executable (PyInstaller).

* **Read-only resources** (the ``static/`` folder) are bundled *inside* the
  executable and extracted to a temp dir at runtime (``sys._MEIPASS``).
* **The database** must live in a *writable, persistent, per-user* location — the
  temp extraction dir is wiped between runs, so a packaged build stores it under
  the OS's per-user data directory instead of next to the code.

In normal (non-frozen) development nothing changes: resources and the database
resolve to the project root exactly as before.
"""
import os
import sys
from pathlib import Path

APP_NAME = "PersonalFinance"


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """Locate a bundled read-only resource (e.g. ``static``).

    When frozen, resources live under ``sys._MEIPASS``; otherwise under the
    project root.
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", _project_root()))
    else:
        base = _project_root()
    return base / relative


def user_data_dir() -> Path:
    """Return (creating if needed) the per-user data directory for this app.

    * Windows: ``%LOCALAPPDATA%\\PersonalFinance``
    * macOS:   ``~/Library/Application Support/PersonalFinance``
    * Linux:   ``$XDG_DATA_HOME/PersonalFinance`` or ``~/.local/share/PersonalFinance``
    """
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    directory = base / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_db_path() -> str:
    """Where the SQLite database lives.

    Priority: explicit ``FINANCE_DB_PATH`` env var → per-user data dir (when
    packaged as an executable) → project root ``finance.db`` (development).
    """
    env = os.environ.get("FINANCE_DB_PATH")
    if env:
        return env
    if is_frozen():
        return str(user_data_dir() / "finance.db")
    return str(_project_root() / "finance.db")
