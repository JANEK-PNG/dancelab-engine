#!/bin/bash
# Terminal na żywo: co się w tej chwili dzieje z analizą korpusu.
S=/Users/jantrybus/Developer/dancelab-engine/data/reports/corpus_features_ext/status.json
while true; do
  clear
  echo "╭─ DANCELAB · analiza korpusu ────────────────────────────────╮"
  if pgrep -f corpus_analyze_ext >/dev/null; then echo "│  stan: PRACUJE                                              │"
  else echo "│  stan: ZATRZYMANE                                           │"; fi
  echo "╰─────────────────────────────────────────────────────────────╯"
  python3 - "$S" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: print("  (jeszcze brak danych)"); raise SystemExit
z,w=d["zrobione"],d["wszystkie"]
p=z/max(w,1); bar="█"*int(p*44)+"·"*(44-int(p*44))
print(f"\n  {bar} {p*100:5.1f}%\n")
print(f"  zrobione      {z} z {w}")
print(f"  tempo         {d['tempo_utw_min']} utworów/min")
print(f"  minęło        {d['minelo_min']:.0f} min")
print(f"  zostało       {d['zostalo_min']/60:.1f} h")
print(f"  błędy         {d['bledy']}")
print(f"\n  ostatni       {d.get('ostatni')}")
print(f"                {d.get('ostatni_bpm')} BPM · {d.get('ostatni_key')}")
print(f"\n  odświeżono    {d['aktualizacja']}   (Ctrl+C = wyjście)")
PY
  sleep 3
done
