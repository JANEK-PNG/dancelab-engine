"""Premia za gatunek — miękkie trzymanie się briefu, gdy twarde sito nie wchodzi.

Do 09.08 preferencja gatunków działała jak wyłącznik: albo zawężała pulę
w całości, albo — gdy pasujących utworów było mniej niż długość setu —
znikała BEZ RESZTY. Jeden utwór poniżej progu i z „trzymaj się House'u"
robiło się „graj cokolwiek" (skarga Janka 09.08: „jeśli mam filary w stylu X,
gatunek w stylu Y i DJ-a w stylu Z, to jak to mamy rozwiązane?").

Ten moduł daje stan pośredni: pula zostaje pełna, ale kandydat o pasującym
gatunku dostaje PREMIĘ do oceny. Set trzyma się gatunku tak długo, jak pula
pozwala, i przestaje dokładnie tam, gdzie musi — zamiast porzucać brief
w całości.

Kształt premii to STAŁY MARGINES: `ocena + w`, przycięte do jedynki. Znaczy
dokładnie tyle: „przy różnicy ocen mniejszej niż w wybierz gatunek z briefu".

Pierwsza wersja przesuwała ocenę ku jedynce (`ocena + w · (1 − ocena)`)
i została odrzucona pomiarem: przy dobrym szwie 0,892 dawała ledwie 0,016
premii, więc dokładnie tam, gdzie silnik pracuje najczęściej, gatunek nie
zmieniał nic. Stały margines działa jednakowo na całej skali.

Słaby szew i tak nie wygra: ryzykowny (0,59) z premią daje 0,74, a dobry
kandydat stoi przy 0,96. Sama waga jest ZMIERZONA na realnej bibliotece —
tabela w komentarzu przy `DOMYSLNA_WAGA`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from dancelab.decision.library_profile import normalize_style_list, style_matches

# Margines rozstrzygania: gatunek wygrywa, gdy przegrywa oceną o mniej niż
# tyle. ZMIERZONE na bibliotece Janka (256 utworów, set na 18, brief „House"
# przy 7 dostępnych utworach tego gatunku) — utworów gatunku w secie / średnia
# ocena szwu:
#   0,00 → 2/7 · 0,9595      0,08 → 2/7 · 0,9688
#   0,15 → 3/7 · 0,9609      0,25 → 3/7 · 0,9504
# 0,15 kupuje utwór gatunku BEZ straty na jakości szwów; 0,25 już tylko
# kosztuje. Powyżej tego premia i tak nie sięgnie dalej — przy 7 utworach
# w puli na 18 slotów gatunek wchodzi tam, gdzie pasuje, i nigdzie indziej.
DOMYSLNA_WAGA = 0.15


@dataclass
class PremiaGatunku:
    """Stan premii na czas budowy jednego setu (jak SoundSteering)."""

    gatunki: list[str] = field(default_factory=list)
    waga: float = DOMYSLNA_WAGA
    trafione: int = 0
    ocenione: int = 0

    @property
    def aktywna(self) -> bool:
        return bool(self.gatunki) and self.waga > 0

    def dopasuj(self, ocena: float, kandydat,
                krawedzie: int = 1) -> tuple[float, str | None]:
        """(ocena po premii, zdanie do uzasadnienia albo None).

        `krawedzie` to liczba przejść zsumowanych w ocenie. Przy slocie tuż
        przed FILAREM silnik sumuje dwie krawędzie (reguła tripletów: kandydat
        musi też umieć wejść w filar), więc i skala ocen, i naturalne różnice
        między kandydatami są tam dwa razy większe. Bez tego mnożnika premia
        byłaby przy filarach o połowę słabsza niż w zwykłym slocie — gatunek
        znaczyłby co innego w różnych miejscach setu.
        """
        if not self.aktywna:
            return ocena, None
        self.ocenione += 1
        if not style_matches(getattr(kandydat.track, "style_label", None),
                             self.gatunki):
            return ocena, None
        self.trafione += 1
        # BEZ przycinania do sufitu: ta liczba jest KLUCZEM PORZĄDKUJĄCYM
        # wewnątrz wyboru następnika, a nie oceną pokazywaną DJ-owi (tę
        # silnik liczy osobno dla gotowego planu). Przycinanie do 1,0
        # kasowało premię dokładnie tam, gdzie biblioteka Janka żyje:
        # zmierzona średnia ocena szwu w jego puli to 0,96, więc premia
        # wpadała w sufit i remis rozstrzygała nazwa pliku.
        po = ocena + self.waga * max(int(krawedzie), 1)
        return float(po), (
            f"premia za gatunek {kandydat.track.style_label} (w={self.waga:.2f})")

    def podsumowanie(self) -> str:
        """Jedno zdanie do ostrzeżeń — ile razy premia w ogóle zadziałała."""
        return (f"premia za gatunek ({', '.join(self.gatunki)}): pasowało "
                f"{self.trafione} z {self.ocenione} ocenianych kandydatów")


def zbuduj(preferencje: Sequence[str] | None,
           waga: float | None = None) -> PremiaGatunku | None:
    """PremiaGatunku albo None, gdy nie ma czego premiować."""
    gatunki = normalize_style_list(preferencje)
    if not gatunki:
        return None
    return PremiaGatunku(gatunki=list(gatunki),
                         waga=DOMYSLNA_WAGA if waga is None else float(waga))
