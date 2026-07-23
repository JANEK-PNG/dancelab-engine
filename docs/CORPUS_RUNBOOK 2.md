# Corpus pipeline — runbook (dla Klaris i Korda)

Jedno źródło prawdy o tym, JAK wznawiać procesy korpusu po padzie/purge.
Aktualizować przy każdej zmianie parametrów.

## Wznowienie po padzie (oba resumable, nic nie liczy się od zera)

Downloader:
```bash
cd /Volumes/MY_PC/DanceLabCorpus && nohup caffeinate -i python3 \
  /Users/jantrybus/Desktop/AI/dancelab-engine/scripts/corpus_downloader.py \
  --root /Volumes/MY_PC/DanceLabCorpus >> logs/resume_dl.log 2>&1 &
```

Alignment (matching) — **workers 5 = uzgodniony standard** (24 GB RAM,
benchmark 2026-07-16; 6+ ryzykuje swap i SPOWALNIA):
```bash
cd /Users/jantrybus/Desktop/AI/dancelab-engine && PYTHONPATH=src nohup \
  caffeinate -i .venv/bin/python scripts/corpus_align.py \
  --root /Volumes/MY_PC/DanceLabCorpus --workers 5 --min-tracks 4 \
  >> /Volumes/MY_PC/DanceLabCorpus/logs/resume_align.log 2>&1 &
```

## Zasady

- Przed startem sprawdź dublety: `pgrep -f corpus_downloader; pgrep -f corpus_align`
  — dwie instancje = wyścig na manifest.csv. Zabij stare przed nowym startem.
- Dashboard: `python3 scripts/corpus_live.py` (podgląd; Ctrl+C nie rusza pipeline'u).
- Status: `scripts/corpus_status.sh`.
- Pełne DTW to decyzja (kaskada okien odrzucona po profilowaniu — patrz
  docs/corpus_predictions.md). Nie "optymalizować" bez nowego pomiaru.
- Etyka korpusu: docs/CORPUS_ETHICS.md (m.in. features-then-delete po analizie).

## Aktualizacja 2026-07-17: pętla samowznawiania matchingu

Alignment jest szybszy niż (rate-limited) downloader i dogania kolejkę,
kończąc pojedynczy przebieg. Zamiast ręcznego wznawiania — pętla:
```bash
nohup caffeinate -i /Users/jantrybus/Desktop/AI/dancelab-engine/scripts/corpus_align_loop.sh \
  >> /Volumes/MY_PC/DanceLabCorpus/logs/align_loop.log 2>&1 &
```
Re-odpala matching co 15 min (workers 5), dobiera mixy w miarę jak dociągają
tracki, kończy dopiero gdy downloader gotowy I nic nie zostało do dopasowania.
Zabij pętlę: `pkill -f corpus_align_loop`.
