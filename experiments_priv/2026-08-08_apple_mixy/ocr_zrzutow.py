"""OCR zrzutów katalogu „Miksy DJ-skie" (Apple Music) → lista miksów.

Vision (macOS) czyta tekst z pozycjami; parsowanie opiera się na twardej
własności UI: tytuł miksu KOŃCZY się na „(DJ Mix)", a wiersz pod nim to DJ.
Kolumny siatki klastrowane po środku X."""

import json
import pathlib
import re

import Quartz
import Vision

KATALOG = pathlib.Path(__file__).parent
ZRZUTY = sorted((KATALOG / "zrzuty").glob("*.png"))
SMIECI = {"Apple Music", "Miksy DJ-skie", "E"}


def linie_z_obrazu(path):
    url = Quartz.CFURLCreateWithFileSystemPath(
        None, str(path), Quartz.kCFURLPOSIXPathStyle, False)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        img, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    handler.performRequests_error_([req], None)
    out = []
    for obs in req.results() or []:
        tekst = obs.topCandidates_(1)[0].string()
        box = obs.boundingBox()
        out.append({"tekst": tekst,
                    "x": box.origin.x + box.size.width / 2,
                    "y": box.origin.y})
    return out


def miksy_z_linii(linie):
    kolumny = {}
    for ln in linie:
        if ln["tekst"].strip() in SMIECI or len(ln["tekst"].strip()) <= 1:
            continue
        kolumny.setdefault(int(ln["x"] / 0.2), []).append(ln)
    znalezione = []
    for kol in kolumny.values():
        kol.sort(key=lambda l: -l["y"])          # od góry ekranu
        tytul: list[str] = []
        czekam_na_dj = False
        for ln in kol:
            t = ln["tekst"].strip()
            if czekam_na_dj:
                znalezione.append({"tytul": " ".join(tytul), "dj": t})
                tytul, czekam_na_dj = [], False
                continue
            tytul.append(t)
            if re.search(r"\(DJ Mix\)\s*$", t) or t.endswith("(DJ"):
                czekam_na_dj = True
    return znalezione


wszystkie = []
for path in ZRZUTY:
    znal = miksy_z_linii(linie_z_obrazu(path))
    wszystkie.extend(znal)
    print(f"{path.name}: {len(znal)} miksów")

unikatowe = {}
for m in wszystkie:
    klucz = re.sub(r"[^a-z0-9]+", "", m["tytul"].lower())
    if klucz not in unikatowe:
        unikatowe[klucz] = m
wynik = sorted(unikatowe.values(), key=lambda m: m["tytul"].lower())
(KATALOG / "miksy_ocr.json").write_text(
    json.dumps(wynik, ensure_ascii=False, indent=1))
print(f"\nRAZEM: {len(wszystkie)} odczytów → {len(wynik)} unikatowych miksów")
print("→", KATALOG / "miksy_ocr.json")
