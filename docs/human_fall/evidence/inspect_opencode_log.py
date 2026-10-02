"""Compact read-only view of CLI events for orchestration/context recovery."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = Path(sys.argv[1])
events = []
for line in path.read_text(encoding="utf-8-sig").splitlines():
    try:
        events.append(json.loads(line))
    except json.JSONDecodeError:
        pass  # The running CLI may not have finished its last line.
for event in events[-6:]:
    part = event.get("part", {})
    state = part.get("state", {})
    print(event.get("type"), part.get("tool", ""), state.get("status", ""),
          state.get("title", ""))
    if event.get("type") == "text":
        print(part.get("text", "")[-1200:])
    if "--output" in sys.argv and part.get("tool") == "bash":
        print(state.get("output", "")[-1200:])
print("EVENTS=" + str(len(events)))
if events:
    print("SESSION=" + str(events[-1].get("sessionID")))
