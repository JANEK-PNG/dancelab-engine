# DanceLab Engine — rules for every agent session

Read this first. It is short on purpose: the real rules already live in the
files it points to, and an agent that is told too much writes worse code.

## 1. What this project is
A local, terminal-first DJ-intelligence engine (Python 3.11+, `src/dancelab`).
The product question: *does this track make sense next, in this set, in this
context?* README.md has the ten-minute quickstart.

## 2. The files that bind you
- `CONTRIBUTING.md` — environment, the quality gate, what a change must carry.
- `docs/DECISIONS.md` — ADR-001..006. **ADR-005 is load-bearing: never
  fabricate a result.** Unimplemented computations raise; unknown values are
  `None` with a warning; every decision output carries explanation, confidence
  and provenance.
- `docs/CORPUS_ETHICS.md` — no audio in the repository, ever.
- `docs/DOCUMENTATION_STANDARD.md` — English for anything a reader is pointed at.
- `OBALONE.md` — what was measured and did not pay. Do not retry it by accident.
- `PROJECT_LEDGER.md` — the owner's log, in Polish. Decisions land there.

## 3. Before you say "done"
Run the gate. All of it. Paste the output in your report.
```bash
./.venv/bin/python -m pytest
./.venv/bin/ruff check src tests scripts
./.venv/bin/python scripts/docstring_coverage.py --check
./.venv/bin/python -m compileall -q src tests
```
A number in a document or commit names the script or artifact it came from.
A number that cannot be traced is removed, not softened.

## 4. Style, naming, commits
- Line length 100 (`ruff`). Public modules, classes and callables have docstrings.
- Pydantic models for every engine output (ADR-004). Core stays framework-free (ADR-003).
- Commit subject: `<area>: <what changed, in one plain sentence>`, lowercase area,
  English. Areas in use: `gui`, `docs`, `ledger`, `cues`, `tui`, `api`, `preview`.
  Example: `gui: one undo stack, an audio check at startup, and an empty start that speaks`.
- Documentation changes in the same commit as the behaviour they describe.

## 5. Working as one of several sessions
This project is worked by parallel sessions, each in its own folder, each in a
Herdr tab. Rules from `~/Developer/ways-of-working`:
- **One writer per folder.** You edit only inside the folder you were started
  in. A change needed elsewhere goes into your report under `AFFECTS`; you do
  not make it. If you were started at the repository root, you are the only
  writer for this tab's task and you still keep to the files your task names.
- **No subagents, no fan-out.** Parallelism is other tabs, started by the owner.
- **Decide alone** when the change is reversible with one command, touches only
  your files and follows what the code already does. Record it in the folder's
  `DECYZJE.md`. **Ask the owner** when it is irreversible, crosses folders,
  changes a contract between modules, or picks a library the code does not
  already use.
- **Report** at the end, in `RAPORT.md` beside your task, ten lines at most:
  `SEKCJA / STATUS / DONE / AFFECTS / BLOCKER / PYTANIA`. Gate output goes in
  `DONE` as a one-line summary (`pytest 214 passed, ruff clean`), not pasted whole.
- **Blind review** of your diff comes from another engine
  (`~/Developer/ways-of-working/bin/przeglad`). Expect it; do not argue with it
  in advance.

## 6. Talking to the owner
Polish, short, plain words. The owner does not read code; the ledger and your
report are the owner's view. Code, commits, docstrings and anything a reader is
pointed at: English (§2, documentation standard).
