"""Set z ekranu → playlista w Rekordboksie. Jedna droga dla obu skór.

Ten moduł nie dopasowuje utworów, nie robi kopii zapasowej i nie pisze do
bazy — to wszystko robi `ingestion.playlist_publish.publish_playlist`, ta
sama funkcja, którą woła terminal. Tutaj siedzi wyłącznie KOLEJNOŚĆ kroków
i przekład setu na ścieżki plików.

Dwa stopnie, jak przy cue: `podglad` liczy dopasowania i mówi, ile utworów
wejdzie oraz **które wypadną i dlaczego** (`dry_run=True`, baza tylko
czytana); `wyslij` dopiero zakłada playlistę.

Dlaczego stopień pierwszy nie jest ozdobą: dopasowanie idzie po ścieżce
pliku, a gdy jej nie ma — po tytule, i tylko wtedy, gdy kandydat jest
DOKŁADNIE jeden. Utwór, którego nie ma w kolekcji Rekordboxa, wypada
imiennie. DJ ma to zobaczyć przed zapisem, nie po.
"""

from __future__ import annotations

from typing import Any


def sciezki(kolejnosc: list[str], analizy: dict) -> tuple[list[str], list[str]]:
    """Set → ścieżki plików, w kolejności. Zwraca też braki, imiennie.

    Utwór bez analizy albo bez ścieżki nie jest zgadywany — trafia na listę
    braków pod własnym identyfikatorem.
    """
    sciezki_: list[str] = []
    braki: list[str] = []
    for tid in kolejnosc:
        analiza = analizy.get(tid)
        sciezka = getattr(getattr(analiza, "track", None), "source_path", None)
        if sciezka:
            sciezki_.append(str(sciezka))
        else:
            braki.append(str(tid))
    return sciezki_, braki


def rekordbox_otwarty() -> bool:
    from dancelab.ingestion.playlist_publish import rekordbox_running
    return bool(rekordbox_running())


def podglad(kolejnosc: list[str], analizy: dict, *,
            nazwa: str) -> dict[str, Any]:
    """Stopień pierwszy: policz dopasowania, NIC nie zapisuj."""
    from dancelab.ingestion.playlist_publish import publish_playlist

    lista, braki = sciezki(kolejnosc, analizy)
    if not lista:
        return {"blad": "żaden utwór setu nie ma ścieżki pliku — "
                        "nie ma czego wysłać"}
    raport = publish_playlist(lista, name=nazwa, dry_run=True)
    return _raport_do_slownika(raport, braki)


def wyslij(kolejnosc: list[str], analizy: dict, *,
           nazwa: str) -> dict[str, Any]:
    """Stopień drugi: załóż playlistę w Rekordboksie."""
    from dancelab.ingestion.playlist_publish import publish_playlist

    lista, braki = sciezki(kolejnosc, analizy)
    if not lista:
        return {"blad": "żaden utwór setu nie ma ścieżki pliku — "
                        "nie ma czego wysłać"}
    raport = publish_playlist(lista, name=nazwa, dry_run=False)
    return _raport_do_slownika(raport, braki)


def _raport_do_slownika(raport, braki_bez_sciezki: list[str]) -> dict[str, Any]:
    """Raport publikacji w postaci, którą widok potrafi wyświetlić.

    Utwory pominięte przez dopasowanie zostają w `notki` własnymi słowami
    warstwy publikującej — przepisywanie ich tutaj rozjechałoby się z tym, co
    widzi terminal.
    """
    wynik = {
        "ok": bool(raport.ok),
        "nazwa": raport.playlist_name,
        "zgloszone": raport.requested,
        "dopasowane": raport.matched,
        "zapisane": raport.written,
        "kopia": raport.backup_path,
        "notki": list(raport.notes),
        "bez_sciezki": braki_bez_sciezki,
    }
    if not raport.ok:
        wynik["blad"] = "; ".join(raport.notes) or "zapis nieudany"
    return wynik
