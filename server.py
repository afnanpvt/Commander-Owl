"""Commander Owl engine: localhost dashboard + rule scheduler. Stdlib only."""
import datetime as dt
import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "state.json")
PORT = 47821
BUSY_STALE = 900   # a "running" session with no hook event or transcript write for this long counts as stalled
MISSED_AFTER = 120  # a clock rule overdue by more than this (server was down) is skipped, not fired
NO_WINDOW = 0x08000000
PROJECTS = os.path.expanduser("~/.claude/projects")
SCAN_WINDOW = 3 * 3600  # transcripts touched within this long are treated as live sessions
QUIET = 60              # a transcript-only session with no writes for this long is considered finished

ACTIONS = {
    "hibernate": ["shutdown", "/h"],
    "shutdown": ["shutdown", "/s", "/t", "0"],
    "sleep": ["powershell", "-NoProfile", "-Command",
              "Add-Type -AssemblyName System.Windows.Forms; "
              "[System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false)"],
    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
}

LOCK = threading.RLock()
S = {"settings": {"dry_run": False}, "sessions": {}, "rules": [], "pending": None, "log": [], "dismissed": []}


def now():
    return time.time()


def save():
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(S, f, indent=1)
    os.replace(tmp, STATE_FILE)


def load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            S.update(json.load(f))
    except (OSError, ValueError):
        return
    if S.get("pending"):  # never resume a countdown across a restart
        S["pending"] = None
        note("Dropped a pending countdown on restart")


def note(msg):
    S["log"].append({"t": now(), "msg": msg})
    del S["log"][:-200]


def hibernate_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power") as k:
            return bool(winreg.QueryValueEx(k, "HibernateEnabled")[0])
    except OSError:
        return None


def session_state(s, t):
    if s.get("ended"):
        return "ended"
    if s["status"] != "running":
        return "idle"
    last = s["last_event"]
    try:
        last = max(last, os.path.getmtime(s["transcript"]))
    except (OSError, KeyError, TypeError):
        pass
    return "working" if t - last < BUSY_STALE else "stalled"


# ---------- rule engine (call with LOCK held) ----------

def next_at(ts, repeat):
    d = dt.datetime.fromtimestamp(ts)
    while d.timestamp() <= now():
        d += dt.timedelta(days=1)
    while repeat == "weekdays" and d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.timestamp()


def consume(rule):
    if rule["kind"] == "time" and rule.get("repeat") in ("daily", "weekdays"):
        rule["at_ts"] = next_at(rule["at_ts"], rule["repeat"])
    else:
        S["rules"] = [r for r in S["rules"] if r["id"] != rule["id"]]


def fire(rule, reason, session_id=None, cancel_on_activity=True):
    if S["pending"]:
        return
    t = now()
    S["pending"] = {
        "rule": dict(rule), "action": rule["action"], "reason": reason, "started": t,
        "grace": rule["grace"], "fires_at": t + rule["grace"],
        "session_id": session_id, "cancel_on_activity": cancel_on_activity,
    }
    if rule["id"] != "manual":
        consume(rule)
    note(f"Armed {rule['action']} in {rule['grace']}s: {reason}")
    if rule["grace"] <= 0:
        threading.Thread(target=execute, daemon=True).start()


def cancel(why, restore=False):
    p = S["pending"]
    if not p:
        return
    S["pending"] = None
    if restore and p["rule"]["kind"] != "time" and p["rule"]["id"] != "manual":
        S["rules"].append(p["rule"])
    note(f"Cancelled {p['action']}: {why}" + (" (rule re-armed)" if restore else ""))


def execute():
    with LOCK:
        p = S["pending"]
        S["pending"] = None
        if not p:
            return
        if S["settings"]["dry_run"]:
            note(f"[dry run] would have run {p['action']}")
            save()
            return
        note(f"Running {p['action']}")
        save()
    try:
        r = subprocess.run(ACTIONS[p["action"]], capture_output=True, text=True,
                           timeout=30, creationflags=NO_WINDOW)
        if r.returncode:
            with LOCK:
                note(f"{p['action']} exited {r.returncode}: {(r.stderr or r.stdout).strip()[:160]}")
                save()
    except Exception as e:  # noqa: BLE001
        with LOCK:
            note(f"{p['action']} failed: {e}")
            save()


def evaluate(sid, kind):
    """kind is 'turn' (a Stop hook fired) or 'end' (session closed)."""
    t = now()
    s = S["sessions"].get(sid, {})
    for r in list(S["rules"]):
        if not r.get("enabled", True):
            continue
        if r["kind"] == "session" and r["session_id"] == sid and (kind == "end" or r["trigger"] == "turn"):
            fire(r, f"{label(s) if s else sid[:8]} {'closed' if kind == 'end' else 'finished its run'}", sid)
        elif r["kind"] == "idle":
            if not any(session_state(x, t) == "working" for x in S["sessions"].values()):
                fire(r, "every session is idle")


def resumed(sid, s):
    pend = S["pending"]
    if pend and pend["cancel_on_activity"] and pend["session_id"] in (None, sid):
        cancel(f"{label(s)} became active again", restore=True)


def peek(path):
    """Read cwd and last real user prompt from the tail of a transcript."""
    cwd, prompt, conv = None, "", ""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return cwd, prompt, conv
    for line in reversed(lines):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        cwd = cwd or o.get("cwd")
        if not conv and o.get("type") == "custom-title":
            conv = o.get("customTitle") or ""
        if not prompt and o.get("type") == "user" and not o.get("isMeta"):
            c = (o.get("message") or {}).get("content")
            if isinstance(c, list):
                c = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                prompt = c.strip().replace("\n", " ")[:140]
        if cwd and prompt and conv:
            break
    return cwd, prompt, conv


def label(s):
    return s.get("conv") or s["name"]


def scan():
    """Find sessions from transcript files, so sessions opened before the hooks existed still show up.
    Hook-reported sessions stay authoritative; the rest are judged by transcript activity."""
    t = now()
    try:
        projects = [d.path for d in os.scandir(PROJECTS) if d.is_dir()]
    except OSError:
        return
    for d in projects:
        try:
            files = [f for f in os.scandir(d) if f.name.endswith(".jsonl") and f.is_file()]
        except OSError:
            continue
        for f in files:
            sid, m = f.name[:-6], f.stat().st_mtime
            if t - m > SCAN_WINDOW or sid in S["dismissed"]:
                continue
            s = S["sessions"].get(sid)
            if s and s.get("_tm") != m:  # transcript changed: refresh the conversation name
                s["_tm"] = m
                s["conv"] = peek(f.path)[2] or s.get("conv", "")
            if s and not s.get("discovered"):
                continue
            if not s:
                cwd, prompt, conv = peek(f.path)
                cwd = cwd or d
                s = S["sessions"][sid] = {
                    "id": sid, "status": "idle", "started": m, "last_event": m, "title": prompt,
                    "conv": conv, "_tm": m,
                    "last_prompt": prompt, "cwd": cwd, "ended": False, "discovered": True,
                    "name": os.path.basename(cwd.rstrip("\\/")) or sid[:8], "transcript": f.path}
            was, s["last_event"] = s["status"], m
            s["status"] = "running" if t - m < QUIET else "idle"
            if was == "idle" and s["status"] == "running":
                resumed(sid, s)
            elif was == "running" and s["status"] == "idle":
                evaluate(sid, "turn")


def on_event(ev):
    sid = ev.get("session_id")
    if not sid:
        return
    t = now()
    name = ev.get("event")
    s = S["sessions"].setdefault(sid, {
        "id": sid, "status": "idle", "started": t, "last_event": t, "title": "", "last_prompt": ""})
    s["last_event"] = t
    s["ended"] = False
    if ev.get("cwd"):
        s["cwd"] = ev["cwd"]
        s["name"] = os.path.basename(ev["cwd"].rstrip("\\/")) or ev["cwd"]
    s.setdefault("name", sid[:8])
    if ev.get("transcript_path"):
        s["transcript"] = ev["transcript_path"]
    if name == "UserPromptSubmit":
        s["status"] = "running"
        p = (ev.get("prompt") or "").strip().replace("\n", " ")[:140]
        if p:
            s["last_prompt"] = p
            s["title"] = s["title"] or p
        resumed(sid, s)
    elif name == "Stop":
        s["status"] = "idle"
        evaluate(sid, "turn")
    elif name == "SessionEnd":
        s["status"] = "idle"
        s["ended"] = True
        evaluate(sid, "end")
    save()


def tick():
    n = 0
    while True:
        time.sleep(1)
        n += 1
        with LOCK:
            if n % 3 == 1:
                scan()
            t = now()
            p = S["pending"]
            if p and t >= p["fires_at"]:
                threading.Thread(target=execute, daemon=True).start()
            for r in list(S["rules"]):
                if r["kind"] == "time" and r.get("enabled", True) and t >= r["at_ts"]:
                    if t - r["at_ts"] > MISSED_AFTER:
                        note(f"Skipped missed clock rule ({r['action']})")
                        consume(r)
                        save()
                    elif not S["pending"]:
                        fire(r, "scheduled time reached", cancel_on_activity=False)
                        save()
            if n % 60 == 0:
                for sid, s in list(S["sessions"].items()):
                    if t - s["last_event"] > (6 * 3600 if s.get("ended") else 3 * 86400):
                        del S["sessions"][sid]
                save()


# ---------- API ----------

def view():
    t = now()
    sessions = [dict(s, state=session_state(s, t)) for s in S["sessions"].values()]
    sessions.sort(key=lambda s: -s["last_event"])
    return {"now": t, "settings": S["settings"], "sessions": sessions, "rules": S["rules"],
            "pending": S["pending"], "log": S["log"][-60:][::-1], "hibernate_enabled": hibernate_enabled()}


def create_rule(b):
    action = b.get("action")
    if action not in ACTIONS:
        raise ValueError("Pick an action")
    grace = int(b.get("grace", 60))
    if not 0 <= grace <= 600:
        raise ValueError("Grace period must be 0 to 600 seconds")
    kind = b.get("kind")
    rule = {"id": uuid.uuid4().hex[:8], "kind": kind, "action": action, "grace": grace,
            "enabled": True, "created": now()}
    if kind == "session":
        sid = b.get("session_id")
        if sid not in S["sessions"]:
            raise ValueError("Pick a session")
        rule.update(session_id=sid, session_name=S["sessions"][sid]["name"],
                    session_title=S["sessions"][sid].get("title", ""),
                    trigger="end" if b.get("trigger") == "end" else "turn")
    elif kind == "idle":
        pass
    elif kind == "time":
        repeat = b.get("repeat") if b.get("repeat") in ("daily", "weekdays") else "once"
        if b.get("minutes"):
            m = int(b["minutes"])
            if not 1 <= m <= 1440:
                raise ValueError("Timer must be 1 to 1440 minutes")
            rule["at_ts"], repeat = now() + m * 60, "once"
        else:
            try:
                hh, mm = map(int, str(b.get("time", "")).split(":"))
                d = dt.datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
            except ValueError:
                raise ValueError("Pick a time") from None
            rule["at_ts"] = next_at(d.timestamp(), repeat)
        rule["repeat"] = repeat
    else:
        raise ValueError("Unknown rule type")
    S["rules"].append(rule)
    note(f"Rule added: {action} ({kind})")
    save()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        return self.headers.get("Host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        if self.path == "/api/state":
            with LOCK:
                return self._send(200, view())
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        # custom header forces a CORS preflight, so other websites cannot drive this from a browser
        if not self._host_ok() or self.headers.get("X-HHUB") != "1":
            return self._send(403, {"error": "forbidden"})
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with LOCK:
                self._route(b)
                save()
                self._send(200, {"ok": True})
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {"error": str(e)})

    def _route(self, b):
        p = self.path
        if p == "/api/event":
            on_event(b)
        elif p == "/api/rules":
            create_rule(b)
        elif p == "/api/rules/delete":
            S["rules"] = [r for r in S["rules"] if r["id"] != b.get("id")]
        elif p == "/api/rules/toggle":
            for r in S["rules"]:
                if r["id"] == b.get("id"):
                    r["enabled"] = not r.get("enabled", True)
        elif p == "/api/cancel":
            cancel("cancelled from dashboard")
        elif p == "/api/fire_now":
            if b.get("action") not in ACTIONS:
                raise ValueError("Pick an action")
            fire({"id": "manual", "kind": "manual", "action": b["action"],
                  "grace": max(0, min(600, int(b.get("grace", 60))))},
                 "started from dashboard", cancel_on_activity=False)
        elif p == "/api/settings":
            S["settings"]["dry_run"] = bool(b.get("dry_run"))
            note("Dry run " + ("on" if S["settings"]["dry_run"] else "off"))
        elif p == "/api/sessions/clear_ended":
            t = now()
            drop = [k for k, v in S["sessions"].items()
                    if v.get("ended") or (v.get("discovered") and v["status"] == "idle" and t - v["last_event"] > 1800)]
            S["dismissed"] = (S["dismissed"] + drop)[-500:]
            for k in drop:
                del S["sessions"][k]
        else:
            raise KeyError("unknown route")


def main():
    load()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        return  # already running
    threading.Thread(target=tick, daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
