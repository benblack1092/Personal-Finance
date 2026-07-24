# Packaging Personal Finance as a Windows executable

This folder builds a standalone **`PersonalFinance.exe`** that runs the whole app
(server + dashboard) with no Python install required. Double-clicking it starts
the local server and opens the dashboard in your browser.

## Get a prebuilt exe (no build needed)

The GitHub Actions workflow **“Build Windows executable”** produces the exe for
you:

- **On demand:** Actions tab → *Build Windows executable* → *Run workflow* →
  download the `PersonalFinance-windows` artifact when it finishes.
- **On release:** push a tag like `v0.1.0` and the exe is attached to the
  GitHub Release automatically.

## Build it yourself on Windows

```powershell
# From the project root, in a Python 3.11 environment:
pip install -r requirements.txt -r requirements-build.txt
pyinstaller packaging/PersonalFinance.spec --noconfirm --clean

# Result:
dist\PersonalFinance.exe
```

Verify the build boots correctly:

```powershell
.\dist\PersonalFinance.exe --selftest   # prints "server responded 200 on /health"
```

## How it works

- **Entry point** — [`launcher.py`](../launcher.py) starts uvicorn on
  `127.0.0.1` (port 8000, or the next free port) and opens the browser.
  `--selftest` boots the server, checks `/health`, and exits (used by CI).
- **Spec** — [`PersonalFinance.spec`](PersonalFinance.spec) bundles the `static/`
  site (including the vendored Chart.js) and collects uvicorn's dynamically
  imported submodules so the frozen app starts cleanly.
- **Where your data lives** — the packaged app stores its database in a
  persistent per-user folder (**`%LOCALAPPDATA%\PersonalFinance\finance.db`** on
  Windows), not inside the exe, so it survives restarts and app updates. Override
  with the `FINANCE_DB_PATH` environment variable. See
  [`app/paths.py`](../app/paths.py).

## Notes

- The build targets **Windows** via the `windows-latest` GitHub runner. The same
  spec also builds a Linux/macOS binary locally if you want one.
- A console window stays open while the app runs — close it to stop the app.
- Windows SmartScreen may warn about an unsigned exe the first time; choose
  *More info → Run anyway*. Code signing is out of scope for this build.
