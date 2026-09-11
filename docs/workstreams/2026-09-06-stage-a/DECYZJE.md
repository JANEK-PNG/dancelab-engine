# Stage A decisions

- 2026-09-06: The owner confirms set preparation from a personal library as the
  primary audience/task. Live visuals and ML retain their separate workstreams.
- Preserve the existing checkout before editing: a verified Git bundle and
  copies of non-ignored untracked files were made outside the repository in the
  session backup directory. This is a local recovery point, not off-machine
  backup of all runtime data.
- Work on `codex/audit-stage-a`, based on `67cd961`. Keep the pre-existing branch
  and the untracked UX reevaluation document intact.
- Plans and verdicts keep their JSON formats and filename prefixes. New files
  receive unique suffixes and exclusive atomic publication. Existing plans
  remain readable; file access is restricted to regular `plan_*.json` files
  directly in the plans directory. Trash does not overwrite an older entry.
- Backend error strings are untrusted text in GUI rendering. Native bridge
  hardening and an evaluated CSP remain further defence-in-depth work; these
  changes do not claim a complete pentest or tested WKWebView exploit chain.
- The UX prototype is a separate review artifact with marked sample data. It
  does not replace the production GUI or change the scoring model.
