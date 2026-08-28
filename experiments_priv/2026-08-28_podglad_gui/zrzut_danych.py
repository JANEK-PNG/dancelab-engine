"""Prawdziwe dane okna → JSON, żeby dało się obejrzeć ekran bez pulpitu.

Janek jest na telefonie, Mac zablokowany, zrzut ekranu łapie ekran blokady.
Ten skrypt liczy DOKŁADNIE to, co liczy most GUI, i zapisuje wynik do JSON-a.
Strona okna wczytuje go potem w przeglądarce zamiast mostu do Pythona —
pliki HTML/CSS/JS są te same, więc to jest render prawdziwego ekranu,
a nie makieta.

Liczby zapisu liczone na KOPII master.db: Rekordbox jest otwarty, a przy nim
zapis na żywej bazie jest (słusznie) zablokowany.
"""

import json
import pathlib
import shutil
import sys
import tempfile

from dancelab.gui.most import Most
from dancelab.stan import zapis_cue

WYNIK = pathlib.Path(__file__).parent / "dane.json"
ZYWA = pathlib.Path.home() / "Library/Pioneer/rekordbox/master.db"


def main() -> int:
    m = Most()
    dane: dict = {}

    b = m.biblioteka(400)
    dane["biblioteka"] = b
    print(f"spis: {len(b.get('utwory') or [])} utworów", flush=True)

    # Filary wyłączone TYLKO na czas podglądu: Janek ma zaznaczony jeden,
    # a reguła projektu wymaga trzech, więc każda budowa kończy się odmową.
    # Podgląd ma pokazać ekran, nie obchodzić regułę — w oknie odmowa zostaje.
    from dancelab.tui import user_store
    user_store.load_state = lambda *a, **k: None

    print("buduję set…", flush=True)
    m.buduj_set({"minuty": 40, "ziarno": "7", "tempo": "100-160"})
    import time
    while True:
        s = m.postep_budowy()
        if s.get("stan") != "trwa":
            break
        print("  ", s.get("etap"), flush=True)
        time.sleep(2)
    dane["set"] = s
    print(f"set: {s.get('stan')}, {len(s.get('utwory') or [])} utworów", flush=True)

    pierwszy = (s.get("utwory") or [{}])[0].get("track_id")
    if pierwszy:
        dane["utwor"] = m.wczytaj_utwor(pierwszy)
        dane["przebieg"] = m.przebieg_utworu(pierwszy)
        dane["pady"] = m.pady(pierwszy)

    dane["stan_rb"] = m.stan_rekordboxa()

    # liczby zapisu — na kopii, bo Rekordbox chodzi
    if ZYWA.exists():
        katalog = pathlib.Path(tempfile.mkdtemp(prefix="dancelab-podglad-"))
        kopia = katalog / "master.db"
        shutil.copy2(ZYWA, kopia)
        try:
            from dancelab.decision.cue_export_models import CuePlan
            w = zapis_cue.przygotuj(m._plan_cue or CuePlan(),
                                    m._edycje, m._analizy,
                                    m._kolejnosc, baza=kopia)
            dane["zapis"] = {k: v for k, v in w.items() if k != "plan"}
        except Exception as exc:                        # noqa: BLE001
            dane["zapis"] = {"blad": f"{type(exc).__name__}: {exc}"}
        finally:
            shutil.rmtree(katalog, ignore_errors=True)
    print("zapis:", dane.get("zapis"), flush=True)

    WYNIK.write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    print(f"zapisane → {WYNIK}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
