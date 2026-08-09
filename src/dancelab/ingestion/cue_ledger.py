"""Rejestr hot cue, które zapisaliśmy MY — po to, żeby móc je odświeżyć.

Problem złapany 09.08 na żywej bazie Janka: polityka „nigdy nie nadpisujemy
padu, który DJ ustawił sam" traktowała jak cudzy TAKŻE nasz własny pad
z poprzedniej wysyłki. Skutek: DJ przesuwał pad w edytorze, wysyłał ponownie
i w Rekordboksie zostawała stara pozycja — na jego danych 8 z 26 padów
odpadało, w tym 2 zablokowane naszym własnym zapisem.

Rozpoznawanie „naszych" po TREŚCI KOMENTARZA byłoby zgadywaniem: komentarze
są konfigurowalne (`configs/cue_labels.yaml`), a w bazie Janka leżą cudze cue
z komentarzami „Mix In"/„Mix Out", łudząco podobnymi do naszych. Dlatego
pewnik: przy każdym udanym zapisie notujemy UUID wiersza DjmdCue, który sami
utworzyliśmy. „Nasze" = UUID jest w tym rejestrze. Wszystko inne — także cue
zapisane przez nas przed powstaniem rejestru — zostaje uznane za cudze
i NIETKNIĘTE. Zawodzimy w stronę bezpieczną.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

SCIEZKA = pathlib.Path("data/exports/cue_rejestr.json")


def wczytaj(sciezka: pathlib.Path | None = None) -> dict:
    """{uuid: {content_id, kind, position_ms, zapisane}} — pusty przy braku."""
    p = pathlib.Path(sciezka or SCIEZKA)
    if not p.exists():
        return {}
    try:
        dane = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}          # uszkodzony rejestr = zero uprawnień, nie awaria
    return dane if isinstance(dane, dict) else {}


def zapamietaj(wpisy: Iterable[dict], *, znacznik: str,
               sciezka: pathlib.Path | None = None) -> int:
    """Dopisz wiersze, które właśnie utworzyliśmy. Zwraca liczbę wpisów."""
    p = pathlib.Path(sciezka or SCIEZKA)
    rejestr = wczytaj(p)
    ile = 0
    for w in wpisy:
        uuid = str(w.get("uuid") or "")
        if not uuid:
            continue
        rejestr[uuid] = {"content_id": str(w.get("content_id")),
                         "kind": int(w.get("kind") or 0),
                         "position_ms": int(w.get("position_ms") or 0),
                         "zapisane": znacznik}
        ile += 1
    if ile:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rejestr, ensure_ascii=False, indent=1))
    return ile


def nasze_pady(istniejace: dict[str, list], rejestr: dict) -> set[tuple[str, int]]:
    """{(ContentID, pad_index)} zajęte przez cue, które SAMI zapisaliśmy.

    `istniejace` to wynik `read_existing_cues` (ExistingCue z UUID-em).
    Dopasowanie po UUID — bez UUID-a pad nigdy nie trafia do wyniku, więc
    brak informacji zawsze znaczy „cudze, nie ruszaj"."""
    znane = set(rejestr)
    wynik: set[tuple[str, int]] = set()
    for cid, cues in istniejace.items():
        for c in cues:
            uuid = getattr(c, "uuid", "") or ""
            if uuid and uuid in znane and c.pad_index is not None:
                wynik.add((str(cid), int(c.pad_index)))
    return wynik
