# Pełne utwory Apple Music w oknie DanceLab — kryterium PRZED pomiarem (2026-09-10)

Pytanie: czy okno (pywebview → WKWebView na macOS) może odtwarzać pełne
strumienie Apple Music przez MusicKit JS v3, czy zostają 30-sekundowe próbki.

Decyzja Janka (formularz): **tylko sprawdzenie, bez dźwięku.** Sonda nie woła
`play`, nie ustawia kolejki, nie ładuje żadnego utworu.

## Co decyduje
MusicKit gra pełne utwory tylko wtedy, gdy przeglądarka ma FairPlay przez EME
(w kodzie MusicKit: `supportsDrm()` / `hasMediaKeySupport()`; bez tego
`previewOnly`). Mierzymy to samo z zewnątrz:

1. `navigator.requestMediaKeySystemAccess('com.apple.fps', …)` — sukces / błąd.
2. `WebKitMediaKeys.isTypeSupported('com.apple.fps.1_0' | 'com.apple.fps.2_0', 'video/mp4')`.
3. Czy MusicKit w ogóle się konfiguruje na danym pochodzeniu strony.

Dwa pochodzenia: `http://localhost` (tak działała autoryzacja w Safari) oraz
`file://` (tak ładuje stronę prawdziwe okno, `gui/okno.py`).

## Werdykt
- **TAK** — punkt 1 sukces i MusicKit się konfiguruje na `file://`.
- **TAK, ale** — jak wyżej tylko na `localhost` → okno musiałoby serwować
  stronę z lokalnego serwera (zmiana architektury okna, decyzja Janka).
- **NIE** — punkt 1 błąd w WKWebView → w oknie zostają próbki 30 s, pełne
  utwory w Rekordboksie. Zapis do OBALONE.md.

## Czego sonda nie rozstrzyga
Stan „zalogowany": nowe okno nie ma tokenu użytkownika, więc `previewOnly`
będzie prawdą niezależnie od DRM. Autoryzacja w oknie to osobny krok, sensowny
tylko przy werdykcie TAK.
