"""Fast import preflight checks before full audio analysis.

Co w bibliotece DJ-a NIE jest płytą, choć jest plikiem audio. Cztery rodzaje:
nagrania własnych setów (40–120 min), cudze miksy ściągnięte do nauki, pętle
i sample (kilka sekund) oraz stemy, które sami wyprodukowaliśmy.

Progi 2–10 min są potwierdzone pomiarem 2026-08-03 na paśmie 130–135 BPM
z biblioteki Janka: prawdziwe płyty rozciągają się od 2:53 do 8:48 przy medianie
4:55, a jedyny odstający plik miał 52:13 (jego własny nagrany set „Open Deck").

Ten moduł ISTNIAŁ i nie był wołany z żadnej ścieżki produktowej — dlatego to
nagranie weszło do pierwszej listy kandydatów na set. Sprawdzenie po długości
jest teraz wołane z `discover_audio_files` i z wyboru kandydatów po briefie.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

MIN_TRACK_DURATION_SEC = 2 * 60.0
MAX_TRACK_DURATION_SEC = 10 * 60.0

# Nazwy plików, które wychodzą z NASZEJ separacji na stemy. Plik nazwany
# dokładnie tak jest naszym produktem ubocznym, nie płytą do zagrania.
STEM_NAMES = frozenset({"vocals", "drums", "bass", "other", "no_vocals", "accompaniment"})

# Katalog, w którym Rekordbox zapisuje to, co DJ ZAGRAŁ. Nagranie setu ma tempo,
# ma tonację i jest plikiem audio — po samych cechach nie różni się od płyty.
_RECORDING_DIR = re.compile(r"(^|/)recordings?(/|$)", re.I)


def suspicious_path_reason(path: str | Path) -> str | None:
    """Powód widoczny po samej ścieżce, bez otwierania pliku — albo None.

    Sprawdzenie po długości wymaga przeczytania nagłówka, a te dwa przypadki
    da się rozstrzygnąć wcześniej i taniej, jeszcze przed listą do analizy.
    """
    p = Path(str(path))
    if p.stem.strip().lower() in STEM_NAMES:
        return "our own stem, not a record"
    if _RECORDING_DIR.search(str(p.parent).replace("\\", "/")):
        return "sits in a recordings folder - a set you played, not a record"
    return None


@dataclass(frozen=True)
class SuspiciousAudioFile:
    path: Path
    duration_sec: float
    reason: str


def probe_audio_duration_sec(path: str | Path) -> float | None:
    """Read duration from file metadata without running the full analysis pipeline."""
    audio_path = Path(path).expanduser()
    try:
        import soundfile as sf

        info = sf.info(str(audio_path))
        if info.samplerate and info.frames:
            return float(info.frames) / float(info.samplerate)
    except Exception:
        pass

    try:
        import librosa

        return float(librosa.get_duration(path=str(audio_path)))
    except Exception:
        return None


def suspicious_duration_reason(
    duration_sec: float | None,
    *,
    min_sec: float = MIN_TRACK_DURATION_SEC,
    max_sec: float = MAX_TRACK_DURATION_SEC,
) -> str | None:
    if duration_sec is None:
        return None
    if duration_sec < min_sec:
        return f"shorter than {min_sec / 60:.0f} minutes"
    if duration_sec > max_sec:
        return f"longer than {max_sec / 60:.0f} minutes"
    return None


def find_suspicious_audio_files(
    files: Sequence[str | Path],
    *,
    duration_probe: Callable[[str | Path], float | None] = probe_audio_duration_sec,
    min_sec: float = MIN_TRACK_DURATION_SEC,
    max_sec: float = MAX_TRACK_DURATION_SEC,
) -> list[SuspiciousAudioFile]:
    suspicious: list[SuspiciousAudioFile] = []
    for source in files:
        path = Path(source).expanduser()
        duration = duration_probe(path)
        reason = suspicious_duration_reason(duration, min_sec=min_sec, max_sec=max_sec)
        if duration is not None and reason is not None:
            suspicious.append(
                SuspiciousAudioFile(
                    path=path,
                    duration_sec=float(duration),
                    reason=reason,
                )
            )
    return suspicious


def format_duration(duration_sec: float) -> str:
    seconds = max(int(round(duration_sec)), 0)
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}:{sec:02d}"
