"""Spina tracklisty z czterech źródeł w jedną bazę, z jawną pewnością połączenia.

Zebrane osobno, bo każde źródło wymagało innego wejścia:

  SoundCloud   6 571 pozycji z komentarzy i opisów, w tym 2 355 z czasem
  MixesDB      110 343 pozycje z 3 793 stron wiki
  NTS Radio    105 145 pozycji z 4 948 odcinków
  hearthis.at  1 283 pozycje z 75 setów

Razem grubo ponad ćwierć miliona pozycji — ale liczba pozycji nie jest tu
miarą wartości. Miarą jest to, czy wiemy, DO KTÓREGO SETU należą.

TRZY STOPNIE PEWNOŚCI POŁĄCZENIA, i to jest sedno tego pliku:

  * `link` — strona zewnętrzna niesie ten sam adres SoundCloud, co nasz wiersz.
    Połączenie jest wtedy faktem, nie wnioskiem. MixesDB podaje go w szablonie
    `{{Player|…}}` i jako jedyne źródło daje tę pewność.
  * `tytul+rok` — zgadza się ksywa ORAZ rok. Mocna poszlaka; przy artyście,
    który w danym roku zagrał raz, praktycznie pewność. Przy rezydencie —
    nie.
  * `nowy` — pozycja, której nie ma czego doczepić: odcinek NTS albo strona
    MixesDB o secie, którego w naszej bazie nie ma. Wchodzi jako NOWY MIKS,
    bo tracklista bez setu jest bezużyteczna, a set z tracklistą to dokładnie
    to, po co tu jesteśmy.

Czego NIE robimy: nie łączymy po samej ksywie. „Ben Klock @ Berghain 2019"
i „Ben Klock @ Garbicz 2019" to dwa różne sety i dwie różne tracklisty;
sklejenie ich zrobiłoby z danych o szwach papkę.
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata as U

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

# Tytuł strony MixesDB ma stały kształt: „RRRR-MM-DD - Artysta @ Impreza,
# Miasto". Stąd bierzemy ksywę i datę do połączenia po tytule.
TYTUL_MDB = re.compile(
    r"^(?P<data>\d{4}(?:-\d{2}){0,2})\s*-\s*(?P<reszta>.+)$")

# Nazwa festiwalu w tytule strony. Wtedy set jest nasz, choćby artysty
# jeszcze nie było na liście — a to znaczy, że przegapiliśmy jego występ.
NASZ_FESTIWAL = re.compile(r"garbicz|audio\s?river|wis[łl]ouj[śs]cie", re.I)


def ksywy_z_tytulu(reszta: str) -> list[str]:
    """Kandydaci na ksywę z członu przed nazwą imprezy.

    Tytuł MixesDB ma kilka układów naraz: „Artysta @ Impreza",
    „Artysta - Cykl 067", „A, B, C - Cykl", „A & B @ Impreza". Tniemy najpierw
    na separatorze imprezy, potem rozdzielamy współwykonawców — bo w duecie
    NASZ może być dopiero drugi.
    """
    czlon = re.split(r"\s+[@|]\s*|\s+-\s+", reszta, maxsplit=1)[0].strip()
    czlon = re.split(r"\s*\(", czlon)[0].strip()
    czesci = re.split(r"\s*(?:,|&|\bb2b\b|\bvs\.?\b|\bfeat\.?\b)\s*",
                      czlon, flags=re.I)
    return [c.strip() for c in ([czlon] + czesci) if len(c.strip()) > 1]


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _link(s: str) -> str:
    return (s or "").split("?")[0].rstrip("/").lower()


def main() -> int:
    miksy = json.loads((OUT / "miksy.json").read_text())
    po_linku = {_link(m.get("link")): m for m in miksy if m.get("link")}
    po_ksywie_roku: dict[tuple[str, str], list[dict]] = {}
    for m in miksy:
        if m.get("ksywa") and m.get("data"):
            po_ksywie_roku.setdefault((_n(m["ksywa"]), str(m["data"])[:4]), []).append(m)

    znani = {_n(a) for a in
             (OUT / "artysci_wszyscy.txt").read_text().splitlines() if a.strip()}

    wynik: list[dict] = []
    licz = {"link": 0, "tytul+rok": 0, "nowy": 0, "odrzucone": 0}

    def dodaj(poz, ksywa, tytul, url, zrodlo, rok=""):
        if not poz:
            return
        cel = None
        sposob = "nowy"
        # 1. adres SoundCloud — połączenie jest faktem
        for p in (url,):
            if _link(p) in po_linku:
                cel, sposob = po_linku[_link(p)], "link"
                break
        # 2. ksywa + rok — mocna poszlaka, ale tylko gdy trafia w JEDEN wiersz
        if cel is None and ksywa and rok:
            kand = po_ksywie_roku.get((_n(ksywa), rok[:4]), [])
            if len(kand) == 1:
                cel, sposob = kand[0], "tytul+rok"
        licz[sposob] += 1
        wynik.append({
            "ksywa": ksywa, "tytul": tytul,
            "link_setu": (cel or {}).get("link") or url,
            "wydarzenie": (cel or {}).get("wydarzenie") or "",
            "data": (cel or {}).get("data") or rok,
            "polaczenie": sposob, "zrodlo_tracklisty": zrodlo,
            "pozycji": len(poz),
            "z_czasem": sum(1 for x in poz if x.get("ms") is not None),
            "tracklista": poz,
        })

    # ── SoundCloud (już połączone po linku z definicji) ──
    if (OUT / "tracklisty.json").exists():
        for w in json.loads((OUT / "tracklisty.json").read_text()):
            dodaj(w["tracklista"], w.get("ksywa"), w.get("tytul"),
                  w.get("link"), "soundcloud", str(w.get("data") or ""))

    # ── MixesDB ──
    nowi_z_festiwali: set[str] = set()
    if (OUT / "tracklisty_mixesdb.json").exists():
        for w in json.loads((OUT / "tracklisty_mixesdb.json").read_text()):
            t = w.get("tytul_strony") or ""
            m = TYTUL_MDB.match(t)
            rok = (m.group("data")[:4] if m else "")
            reszta = (m.group("reszta") if m else t)
            ksywy = ksywy_z_tytulu(reszta)
            nasz = next((k for k in ksywy if _n(k) in znani), None)

            # Strona o secie z NASZEGO festiwalu jest cenna nawet wtedy, gdy
            # artysty nie mamy jeszcze na liście — bo to znaczy, że przegapiliśmy
            # jego występ. „Tibi Dabo @ Garbicz Festival, Poland" był tak
            # odrzucany, choć jest dokładnie tym, czego szukamy.
            fest = NASZ_FESTIWAL.search(t)
            if nasz is None and fest and ksywy:
                nasz = ksywy[0]
                nowi_z_festiwali.add(nasz)
            if nasz is None:
                licz["odrzucone"] += 1
                continue
            dodaj(w["tracklista"], nasz, t,
                  w.get("link_zrodlowy") or w.get("url_mixesdb"), "mixesdb", rok)

    # ── NTS ──
    if (OUT / "tracklisty_nts.json").exists():
        for w in json.loads((OUT / "tracklisty_nts.json").read_text()):
            a = w.get("artysta_szukany") or ""
            if _n(a) not in znani:
                licz["odrzucone"] += 1
                continue
            dodaj(w["tracklista"], a, w.get("tytul_strony") or "",
                  w.get("url_mixesdb"), "nts")

    # ── hearthis ──
    if (OUT / "tracklisty_hearthis.json").exists():
        for w in json.loads((OUT / "tracklisty_hearthis.json").read_text()):
            if not w.get("tracklista"):
                continue
            a = w.get("artysta_szukany") or ""
            if _n(a) not in znani:
                licz["odrzucone"] += 1
                continue
            dodaj(w["tracklista"], a, w.get("tytul_strony") or "",
                  w.get("link_zrodlowy"), "hearthis")

    p = OUT / "tracklisty_wszystkie.json"
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))

    import collections
    print(f"tracklist razem: {len(wynik)}")
    print(f"pozycji razem:   {sum(w['pozycji'] for w in wynik)}")
    print(f"  z czasem:      {sum(w['z_czasem'] for w in wynik)}")
    print("\npewność połączenia z naszym setem:")
    for k in ("link", "tytul+rok", "nowy"):
        print(f"  {k:12s} {licz[k]:6d}")
    print(f"  odrzucone (artysta spoza bazy): {licz['odrzucone']}")
    if nowi_z_festiwali:
        print(f"\nartyści ZŁAPANI z naszych festiwali, których nie mieliśmy "
              f"na liście: {len(nowi_z_festiwali)}")
        print("  " + ", ".join(sorted(nowi_z_festiwali)[:14]))
        (OUT / "artysci_z_mixesdb.txt").write_text(
            "\n".join(sorted(nowi_z_festiwali)))
    print("\nwg źródła:", dict(collections.Counter(w["zrodlo_tracklisty"] for w in wynik)))
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
