"""Collect read-only desktop planning evidence; run from the repository root."""
import ast
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import platform
import subprocess

from dancelab.gui.most import Most
from dancelab.stan import plan
from dancelab.tui import plan_store, user_store
from dancelab.tui.zrodlo import zrodlo

root = Path.cwd()
out = Path(__file__).resolve().parent
bridge = Most()
data = bridge.biblioteka(100000)
rows = data.get("utwory", [])
files = list(Path(bridge._katalog).glob("*.json"))
state = user_store.load_state(bridge._katalog)
plans = plan_store.list_plans()
metadata = {
    "observed_at": datetime.now().astimezone().isoformat(),
    "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "python": platform.python_version(), "platform": platform.platform(),
    "scope": "Read-only headers/state; no audio scan, model inference or Rekordbox write.",
    "library": {
        "configured_path": bridge._katalog, "analysis_json_files": len(files),
        "analysis_json_bytes": sum(p.stat().st_size for p in files),
        "gui_header_rows": len(rows), "gui_reported_total": data.get("wszystkich"),
        "duplicate_track_ids": sum(v - 1 for v in Counter(r["track_id"] for r in rows).values()
                                   if v > 1),
        "missing_bpm_headers": sum(r.get("bpm") is None for r in rows),
        "missing_key_headers": sum(not r.get("tonacja") for r in rows),
        "source_categories": dict(Counter(zrodlo(r.get("sciezka")) for r in rows)),
        "gui_playable_flags": sum(bool(r["grywalny"]) for r in rows),
        "existing_regular_files": sum(Path(str(r.get("sciezka") or "")).is_file()
                                      for r in rows),
        "source_vs_playable_flag": dict(Counter(
            f"{zrodlo(r.get('sciezka'))}/flag={r['grywalny']}" for r in rows)),
        "file_delta_explanation": "library_manifest.json is a manifest with top-level tracks, "
                                  "not a track analysis; inspected directly.",
        "note": "Raw headers. Source categories use zrodlo(); GUI playable flag uses "
                "ma_plik(), which checks an absolute-path prefix, not file existence.",
    },
    "personal_state": {
        "scoped_file": str(user_store.sciezka_stanu(bridge._katalog).resolve().relative_to(root)),
        "file_exists": user_store.sciezka_stanu(bridge._katalog).exists(),
        "playlists": len(state["playlisty"]),
        "favorite_tracks": len(state["ulubione_utwory"]),
        "active_playlist_index": state["aktywna_playlista"],
        "active_pillars": len(user_store.filary_wpisy(state)),
    },
    "saved_plans": {
        "files": len(plans),
        "marked_damaged": sum(str(p["nazwa"]).startswith("USZKODZONY:") for p in plans),
        "pointer_exists": plan.WSKAZNIK.exists(),
        "pointer_target_exists": plan.sciezka_biezacego() is not None,
        "note": "List/read only; no full-pool matching or restore performed.",
    },
    "empty_manual_insert": Most().dopisz_utwor(0, "synthetic-track"),
    "files": {},
}
for name in ["src/dancelab/gui/most.py", "src/dancelab/gui/statyczne/app.js",
             "src/dancelab/tui/app.py", "src/dancelab/gui/okno.py"]:
    metadata["files"][name] = {"lines": len((root / name).read_text().splitlines())}
(out / "inventory.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
api = []
for cls in ast.parse((root / "src/dancelab/gui/most.py").read_text()).body:
    if isinstance(cls, ast.ClassDef) and cls.name == "Most":
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and not fn.name.startswith("_"):
                api.append({"name": fn.name, "line": fn.lineno,
                            "signature": ast.unparse(fn.args)})
(out / "bridge-inventory.json").write_text(json.dumps(api, indent=2) + "\n")
print(json.dumps(metadata, ensure_ascii=False, indent=2))
print("Public bridge methods:", len(api))
