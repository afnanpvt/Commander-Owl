"""Idempotently add the Hibernate Hub hooks to ~/.claude/settings.json (backs it up first)."""
import json, os, shutil, time
P = os.path.expanduser("~/.claude/settings.json")
CMD = 'python "' + os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.py").replace("\\", "/") + '"'
shutil.copy(P, P + f".bak-{int(time.time())}")
d = json.load(open(P, encoding="utf-8"))
h = d.setdefault("hooks", {})
for ev in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
    groups = h.setdefault(ev, [])
    if any("hibernate-hub" in x.get("command", "") for g in groups for x in g.get("hooks", [])):
        continue
    groups.append({"matcher": "", "hooks": [{"type": "command", "command": CMD, "timeout": 10}]})
json.dump(d, open(P, "w", encoding="utf-8"), indent=2)
print("hooks installed:", CMD)
