"""Unifikacja języka interfejsu (Janek, 05.08: „ujednolićmy wszystko na polski").

Silnik mówi po angielsku (konwencja kodu i testów — tego nie ruszamy),
użytkownik czyta po polsku. Tłumaczenie dzieje się w JEDNYM miejscu, na
granicy interfejsu: każda linia trafiająca na ekran przechodzi przez
`po_polsku()`. Znane komunikaty są tłumaczone wzorcami; nieznane przechodzą
BEZ ZMIAN — lepszy angielski oryginał niż zmyślone tłumaczenie (ADR-005).
"""

from __future__ import annotations

import re

_WZORCE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^removed (\d+) duplicate audio file\(s\) \(same bytes\): (.*)$"),
     r"duplikaty (te same bajty) usunięte z puli: \1 — \2"),
    (re.compile(r"^BPM range applied \((.+?)\); (\d+) out-of-range track\(s\) left out.*$"),
     r"okno tempa \1 — poza oknem zostało: \2"),
    (re.compile(r"^BPM range relaxed - not enough analyzed tracks match (.*)$"),
     r"okno tempa POLUZOWANE — za mało utworów pasuje: \1"),
    (re.compile(r"^artist diversity relaxed - repeated artist\(s\): (.*)$"),
     r"różnorodność artystów poluzowana — powtórzeni: \1"),
    (re.compile(r"^artist diversity warning - adjacent repeated artist\(s\): (.*)$"),
     r"uwaga: ten sam artysta na sąsiednich pozycjach: \1"),
    (re.compile(r"^build arc relaxed - energy drop exceeded 8% before position\(s\): (.*)$"),
     r"łuk energii poluzowany — spadek >8% przed pozycją: \1"),
    (re.compile(r"^style preference relaxed - not enough analyzed tracks match (.*)$"),
     r"preferencja gatunków POLUZOWANA — za mało utworów pasuje: \1"),
    (re.compile(r"^risky key change — consider an echo-out / effect transition$"),
     "ryzykowna zmiana tonacji — rozważ echo-out albo przejście efektem"),
    (re.compile(r"^need >=2 tracks to build a set$"),
     "do setu trzeba co najmniej 2 utworów"),
    (re.compile(r"^current track was removed from candidate pool$"),
     "bieżący utwór wyjęty z puli kandydatów"),
    (re.compile(r"^recent-history tracks were removed from candidate pool$"),
     "utwory z niedawnej historii wyjęte z puli"),
    (re.compile(r"^target_track_count cannot exceed the number of available tracks$"),
     "żądana długość przekracza liczbę utworów w puli"),
    (re.compile(r"^locked/pinned tracks exceed target_track_count$"),
     "filarów/zablokowanych więcej niż miejsc w secie"),
    (re.compile(r"^pinned_track_ids reference unknown tracks: (.*)$"),
     r"filar wskazuje utwór spoza puli: \1"),
    (re.compile(r"^start_track_id .* is unknown and was ignored$"),
     "wskazany utwór startowy nieznany — pominięty"),
]


def po_polsku(line: str) -> str:
    """Przetłumacz znany komunikat; nieznany zwróć bez zmian."""
    for wzorzec, zamiana in _WZORCE:
        m = wzorzec.match(line)
        if m:
            return wzorzec.sub(zamiana, line)
    return line
