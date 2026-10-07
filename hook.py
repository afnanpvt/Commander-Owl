"""Claude Code hook: forwards session events to the Hibernate Hub engine. Never blocks or fails."""
import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = 47821
HERE = os.path.dirname(os.path.abspath(__file__))


def post(data):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/event", data=data,
        headers={"X-HHUB": "1", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()


def start_server():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    subprocess.Popen([w if os.path.exists(w) else exe, os.path.join(HERE, "server.py")],
                     creationflags=0x00000008 | 0x00000200 | 0x08000000,  # detached, new group, no window
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    try:
        p = json.load(sys.stdin)
        data = json.dumps({
            "event": p.get("hook_event_name"), "session_id": p.get("session_id"),
            "cwd": p.get("cwd"), "prompt": p.get("prompt"),
            "transcript_path": p.get("transcript_path")}).encode()
    except Exception:  # noqa: BLE001
        return
    try:
        post(data)
        return
    except Exception:  # noqa: BLE001
        start_server()
    for _ in range(15):
        time.sleep(0.2)
        try:
            post(data)
            return
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
