"""Synchronizacja okładek — iTunes Search API → tagi plików → Rekordbox → CDJ.

Łańcuch Janka (06.08): grafika osadzona w pliku → Rekordbox ją czyta →
ekran CDJ-3000 ją wyświetla. To odtworzenie starych narzędzi „iTunes artwork
finder": darmowe API wyszukiwania Apple, wysoka rozdzielczość, zapis do tagów.

Zasady twarde:
* okładka wchodzi TYLKO przy pewnym dopasowaniu artysty i tytułu —
  niejednoznaczność = pominięcie z imiennym powodem (zła okładka na CDJ
  to obciach; wolimy brak niż zmyłkę);
* zapis do tagów z weryfikacją ODCZYTEM po zapisie i z zachowaniem daty
  modyfikacji pliku (cache LUFS/analiz nie unieważniają się hurtowo);
* audio nietknięte — mutagen dopisuje wyłącznie tag z obrazkiem;
* Rekordbox NIE odświeży okładek sam: po synchronizacji trzeba w RB dać
  „Reload Tags" na utworach (można hurtem) — dopiero wtedy okładki jadą
  na eksport USB i ekrany.

HTTP i osadzanie są wstrzykiwalne — testy nie dotykają sieci ani plików.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

RAPORT = pathlib.Path("data/exports/artwork_raport.json")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def _http(url: str) -> bytes:
    zapytanie = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(zapytanie, timeout=20) as odp:
        return odp.read()


def _norm(s: str) -> str:
    s = re.sub(r"\((original|extended|radio|club)[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _pasuje(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na and nb) and (na in nb or nb in na)


def szukaj_okladki(artysta: str, tytul: str,
                   http=_http) -> tuple[str | None, str]:
    """(url okładki 600×600, powód). Pewne dopasowanie albo nic."""
    if not artysta or not tytul:
        return None, "brak wykonawcy/tytułu do wyszukania"
    fraza = urllib.parse.quote(f"{artysta} {tytul}")
    url = (f"https://itunes.apple.com/search?term={fraza}"
           f"&media=music&entity=song&limit=8")
    try:
        wyniki = json.loads(http(url)).get("results", [])
    except Exception as exc:  # noqa: BLE001
        return None, f"iTunes nie odpowiedział: {exc}"
    if not wyniki:
        return None, "nie znaleziono w iTunes"
    for w in wyniki:
        if _pasuje(artysta, w.get("artistName", "")) \
                and _pasuje(tytul, w.get("trackName", "")):
            art = w.get("artworkUrl100", "")
            if art:
                return art.replace("100x100", "600x600"), "dopasowane"
    pierwsi = ", ".join(f"{w.get('artistName')} – {w.get('trackName')}"
                        for w in wyniki[:2])
    return None, f"niejednoznaczne (iTunes proponuje: {pierwsi[:80]})"


def osadz_okladke(path: str, obraz: bytes) -> str | None:
    """Osadź obrazek w tagach pliku; weryfikacja odczytem; mtime zachowany.
    Zwraca powód błędu albo None."""
    import mutagen
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, ID3NoHeaderError
    from mutagen.mp4 import MP4, MP4Cover

    st = os.stat(path)
    suffix = pathlib.Path(path).suffix.lower()
    try:
        if suffix in (".mp3", ".aif", ".aiff", ".wav"):
            plik = mutagen.File(path)
            if plik is None:
                return "mutagen nie rozpoznał pliku"
            if plik.tags is None:
                plik.add_tags()
            plik.tags.delall("APIC") if hasattr(plik.tags, "delall") else None
            plik.tags.add(APIC(encoding=3, mime="image/jpeg", type=3,
                               desc="Cover", data=obraz))
            plik.save()
        elif suffix in (".m4a", ".mp4"):
            plik = MP4(path)
            plik["covr"] = [MP4Cover(obraz, imageformat=MP4Cover.FORMAT_JPEG)]
            plik.save()
        elif suffix == ".flac":
            plik = FLAC(path)
            pic = Picture()
            pic.type = 3
            pic.mime = "image/jpeg"
            pic.data = obraz
            plik.clear_pictures()
            plik.add_picture(pic)
            plik.save()
        else:
            return f"format {suffix} bez obsługi okładek"
    except ID3NoHeaderError:
        return "plik bez nagłówka ID3"
    except Exception as exc:  # noqa: BLE001
        return f"zapis tagu nie wyszedł: {exc}"
    finally:
        try:
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        except OSError:
            pass
    from dancelab.tui.okladki import _bajty_okladki
    if not _bajty_okladki(path):
        return "weryfikacja odczytem: okładki nadal brak"
    return None


def synchronizuj(analyses, *, progress=None, should_stop=None,
                 http=_http, osadz=osadz_okladke,
                 przerwa_sek: float = 0.4) -> dict:
    """Uzupełnij brakujące okładki w plikach. Zwraca i zapisuje raport."""
    from dancelab.tui.app import _wykonawca_tytul
    from dancelab.tui.okladki import _bajty_okladki

    braki = [a for a in analyses
             if not _bajty_okladki(str(a.track.source_path))]
    raport = {"osadzone": [], "niejednoznaczne": [], "nieznalezione": [],
              "bledy": [], "z_okladka_juz": len(analyses) - len(braki)}
    for i, a in enumerate(braki):
        if should_stop and should_stop():
            break
        path = str(a.track.source_path)
        artysta, tytul = _wykonawca_tytul(a.track)
        url, powod = szukaj_okladki(artysta, tytul, http=http)
        if url is None:
            klucz = ("niejednoznaczne" if powod.startswith("niejedno")
                     else "nieznalezione")
            raport[klucz].append({"plik": path, "powod": powod})
        else:
            try:
                obraz = http(url)
                blad = osadz(path, obraz)
            except Exception as exc:  # noqa: BLE001
                blad = f"pobranie nie wyszło: {exc}"
            if blad:
                raport["bledy"].append({"plik": path, "powod": blad})
            else:
                raport["osadzone"].append(path)
        if progress:
            progress(i + 1, len(braki), path)
        time.sleep(przerwa_sek)
    RAPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPORT.write_text(json.dumps(raport, ensure_ascii=False, indent=1))
    return raport
