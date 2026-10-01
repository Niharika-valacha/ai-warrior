"""Write stage-safe snapshots into the web app, and the content seed file for git.

Run after changing system code or editing content:  .venv/bin/python export_snapshots.py
 - web/data/xray-snapshot.json     X-ray for every level (replay model, deterministic)
 - web/data/content-snapshot.json  quiz content, used if the API is down when the page loads
 - web/data/sidequests-snapshot.json  every side quest generated so far (open them all while rehearsing)
 - api/data/content.seed.json      quiz content as JSON, so edits show up in git diffs
"""
import json
from pathlib import Path

import content
import demos
import sidequests

WEB_DATA = Path(__file__).parent.parent / "web" / "data"


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {path}")


with content.connect() as conn:
    current = content.read_all(conn)
    quests = [q for lvl in current["levels"] if (q := sidequests.cached(conn, lvl["id"]))]

write(WEB_DATA / "xray-snapshot.json", [demos.run(level, live=False) for level in range(len(demos.DEMOS))])
write(WEB_DATA / "content-snapshot.json", current)
write(WEB_DATA / "sidequests-snapshot.json", quests)
print(f"  {len(quests)} of {len(current['levels'])} side quests generated so far")
content.export_seed(current)
print(f"wrote {content.SEED}")
