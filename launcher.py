"""Desktop launcher for Personal Finance.

This is the entry point PyInstaller bundles into the executable. It starts the
local web server on 127.0.0.1 and opens the dashboard in the default browser, so
double-clicking the app "just works" with no terminal.

Run modes:
    python launcher.py            # start the app + open the browser
    python launcher.py --selftest # boot the server, hit /health, exit (used by CI)
"""
import socket
import sys
import threading
import time
import urllib.request

import uvicorn

from app.main import app

HOST = "127.0.0.1"
PREFERRED_PORT = 8000


def _pick_port() -> int:
    """Use 8000 if free, otherwise let the OS hand us any open port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, PREFERRED_PORT))
            return PREFERRED_PORT
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _open_browser_when_ready(url: str) -> None:
    """Poll /health, then open the browser once the server is accepting."""
    import webbrowser

    for _ in range(60):
        try:
            with urllib.request.urlopen(url + "/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:  # noqa: BLE001 - server not up yet
            time.sleep(0.25)
    webbrowser.open(url)


def _selftest() -> int:
    """Boot the server in a thread and confirm it serves /health. CI uses this to
    verify the packaged executable actually starts (catches missing imports)."""
    port = _pick_port()
    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=1) as resp:
                    if resp.status == 200:
                        print("selftest: server responded 200 on /health")
                        return 0
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        print("selftest: server did not become healthy in time", file=sys.stderr)
        return 1
    finally:
        server.should_exit = True


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    port = _pick_port()
    url = f"http://{HOST}:{port}"
    print(f"Personal Finance is running at {url}")
    print("Close this window to stop the app.")
    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
