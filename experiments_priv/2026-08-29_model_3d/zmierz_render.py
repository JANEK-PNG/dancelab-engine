"""Sprawdzian renderu: czy z modelu 3D wychodzą te same wymiary co z instrukcji.

Kryterium zapisane w `rendery.py` PRZED renderem:

| co | z instrukcji | tolerancja |
|---|---|---|
| talerz jog | ⌀ 202,2 mm | ±2 mm |
| ekran z ramką | 199,5 × 108,8 mm | ±2 mm |
| listwa ośmiu padów | 268,5 × 18,8 mm | ±2 mm |

Wszystkie trzy muszą się zmieścić, żeby wolno było czytać z tego renderu pozycje
pozostałych kontrolek. Jedno pudło = render zostaje materiałem, a geometria
wraca na raster ±1 mm.

Skrypt jest osobny od renderującego celowo: gdyby był w jednym, kusiłoby, żeby
kręcić kadrem aż liczby się zgodzą.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from PIL import Image
from scipy import ndimage

TU = pathlib.Path(__file__).resolve().parent
OBRAZ = TU / "render" / "cdj_z_gory_orto.png"
SZEROKOSC_MM = 329.0

Z_INSTRUKCJI = {
    "talerz (średnica)": (202.2, 2.0),
    "ekran (szerokość)": (199.5, 2.0),
    "ekran (wysokość)": (108.8, 2.0),
    "listwa hot cue (szerokość)": (268.5, 2.0),
    "listwa hot cue (wysokość)": (18.8, 2.0),
}


def maska_urzadzenia(rgb: np.ndarray) -> np.ndarray:
    """Piksele urządzenia = te, które odstają od jednolitego tła kadru."""
    tlo = np.median(rgb[:12, :12].reshape(-1, 3), axis=0)
    return np.abs(rgb.astype(int) - tlo.astype(int)).sum(axis=2) > 18


def main() -> int:
    if not OBRAZ.exists():
        print(f"BŁĄD: brak {OBRAZ}")
        return 2
    im = Image.open(OBRAZ).convert("RGB")
    rgb = np.asarray(im)
    h, w, _ = rgb.shape
    print(f"render: {w} × {h} px")

    m = maska_urzadzenia(rgb)
    xs = np.nonzero(m.any(axis=0))[0]
    ys = np.nonzero(m.any(axis=1))[0]
    panel = (xs.min(), ys.min(), xs.max(), ys.max())
    px_mm = (panel[2] - panel[0] + 1) / SZEROKOSC_MM
    glab_mm = (panel[3] - panel[1] + 1) / px_mm
    print(f"panel na obrazie: {panel[2] - panel[0] + 1} × {panel[3] - panel[1] + 1} px")
    print(f"skala: {px_mm:.3f} px/mm  ·  głębokość wychodzi {glab_mm:.1f} mm "
          f"(z instrukcji 453,0)")

    szary = rgb.mean(axis=2)
    maks = rgb.max(axis=2).astype(int)
    mini = rgb.min(axis=2).astype(int)
    nasyc = np.where(maks > 0, (maks - mini) / np.maximum(maks, 1), 0)

    def do_mm(px: float) -> float:
        return px / px_mm

    wyniki: dict[str, float] = {}

    def najwieksza_bryla(maska: np.ndarray) -> tuple[int, int, int, int] | None:
        """Obwiednia największego spójnego obszaru — bez tego łapaliśmy sumę
        rozrzuconych plamek po całym panelu i „ekran" wychodził szerszy niż
        panel, co jest niemożliwe i było pierwszym sygnałem, że zepsuty jest
        miernik, a nie render."""
        et, ile = ndimage.label(maska)
        if not ile:
            return None
        rozmiary = ndimage.sum(maska, et, range(1, ile + 1))
        naj = int(np.argmax(rozmiary)) + 1
        ys_, xs_ = np.nonzero(et == naj)
        return xs_.min(), ys_.min(), xs_.max(), ys_.max()

    # --- ekran: największa spójna jasna bryła w górnej połowie panelu ---
    gora = szary[: h // 2, :]
    prog = np.percentile(gora[m[: h // 2, :]], 90)
    b = najwieksza_bryla(gora > prog)
    if b:
        wyniki["ekran (szerokość)"] = do_mm(b[2] - b[0] + 1)
        wyniki["ekran (wysokość)"] = do_mm(b[3] - b[1] + 1)

    # --- listwa hot cue: osiem barwnych padów w jednym rzędzie ---
    barwne = (nasyc > 0.35) & (szary > 25)
    barwne[int(h * 0.45):, :] = False           # dół to talerz i PLAY/CUE
    et, ile = ndimage.label(barwne)
    if ile:
        plamki = []
        for i, w_ in enumerate(ndimage.find_objects(et), 1):
            ys_, xs_ = w_
            pole = (ys_.stop - ys_.start) * (xs_.stop - xs_.start)
            if pole < 200:
                continue
            plamki.append((( ys_.start + ys_.stop) / 2, xs_.start, xs_.stop,
                           ys_.start, ys_.stop))
        if plamki:
            # rząd = plamki o zbliżonym środku w pionie, największa taka grupa
            plamki.sort()
            najlepszy, ile_naj = None, 0
            for p0 in plamki:
                grupa = [q for q in plamki if abs(q[0] - p0[0]) < 12 * px_mm]
                if len(grupa) > ile_naj:
                    najlepszy, ile_naj = grupa, len(grupa)
            if najlepszy:
                wyniki["listwa hot cue (szerokość)"] = do_mm(
                    max(q[2] for q in najlepszy) - min(q[1] for q in najlepszy))
                wyniki["listwa hot cue (wysokość)"] = do_mm(
                    max(q[4] for q in najlepszy) - min(q[3] for q in najlepszy))
                print(f"listwa hot cue: {ile_naj} barwnych plamek w rzędzie")

    # --- talerz: środek z barwnego logo, promień z profilu krawędzi ---
    dol = slice(int(h * 0.45), h)
    nas_dol = nasyc[dol, :] > 0.30
    b2 = najwieksza_bryla(nas_dol)
    if b2:
        cx = (b2[0] + b2[2]) // 2
        cy = (b2[1] + b2[3]) // 2 + dol.start
        gy, gx = np.gradient(szary)
        krawedz = np.hypot(gx, gy)
        promienie = np.arange(int(30 * px_mm), int(125 * px_mm))
        katy = np.linspace(0, 2 * np.pi, 1440, endpoint=False)
        profil = []
        for r in promienie:
            px_ = np.clip((cx + r * np.cos(katy)).astype(int), 0, w - 1)
            py_ = np.clip((cy + r * np.sin(katy)).astype(int), 0, h - 1)
            profil.append(krawedz[py_, px_].mean())
        profil = np.array(profil)
        # wszystkie wyraźne pierścienie, nie tylko najsilniejszy — talerz ma
        # kilka współśrodkowych krawędzi i trzeba je zobaczyć wszystkie
        szczyty = [(promienie[i], profil[i]) for i in range(2, len(profil) - 2)
                   if profil[i] == profil[max(0, i - 12): i + 13].max()
                   and profil[i] > profil.mean() * 1.3]
        szczyty.sort(key=lambda t: -t[1])
        print("pierścienie wykryte na talerzu (średnica mm · siła krawędzi):")
        for r, sila in szczyty[:6]:
            print(f"   ⌀{do_mm(2 * r):6.1f}  {sila:6.1f}")
        if szczyty:
            wyniki["talerz (średnica)"] = do_mm(2 * szczyty[0][0])
        print(f"środek talerza: ({do_mm(cx - panel[0]):.1f}, "
              f"{do_mm(cy - panel[1]):.1f}) mm od rogu panelu")

    print(f"\n{'wielkość':<28} {'z renderu':>10} {'z instrukcji':>13} "
          f"{'różnica':>9}  werdykt")
    zdane = 0
    for nazwa, (oczekiwane, tol) in Z_INSTRUKCJI.items():
        if nazwa not in wyniki:
            print(f"{nazwa:<28} {'—':>10} {oczekiwane:>13.1f} {'—':>9}  NIE ZMIERZONO")
            continue
        w_r = wyniki[nazwa]
        roz = w_r - oczekiwane
        ok = abs(roz) <= tol
        zdane += ok
        print(f"{nazwa:<28} {w_r:>10.1f} {oczekiwane:>13.1f} {roz:>+9.1f}  "
              f"{'zgadza się' if ok else 'POZA TOLERANCJĄ'}")

    werdykt = ("render wolno użyć do geometrii"
               if zdane == len(Z_INSTRUKCJI)
               else "render zostaje materiałem; geometria wraca na raster ±1 mm")
    print(f"\nzdanych sprawdzianów: {zdane}/{len(Z_INSTRUKCJI)} → {werdykt}")

    (TU / "sprawdzian_renderu.json").write_text(json.dumps(
        {"px_na_mm": round(float(px_mm), 3), "glebokosc_mm": round(float(glab_mm), 1),
         "zmierzone": {k: round(float(v), 1) for k, v in wyniki.items()},
         "z_instrukcji": {k: v[0] for k, v in Z_INSTRUKCJI.items()},
         "zdanych": int(zdane), "z_ilu": len(Z_INSTRUKCJI), "werdykt": werdykt},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
