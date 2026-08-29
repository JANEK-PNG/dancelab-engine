"""Kto się myli: model 3D czy mój pomiar talerza z instrukcji.

## Spór

| źródło | średnica talerza |
|---|---|
| siatka modelu 3D (rozdzielona na części) | **207,4 mm** |
| render ortograficzny z modelu (profil krawędzi) | **207,7 mm** |
| mój pomiar z rastra instrukcji (obwiednia kształtu) | **202,2 mm** |

Dwa pomiary z modelu zgadzają się ze sobą co do 0,3 mm i oba odstają od mojego
o ponad 5 mm. Model był skalowany szerokością panelu (329 mm) i jego głębokość
wyszła 454,1 wobec 453,0 z instrukcji — czyli proporcje ma dobre. Podejrzenie
pada więc na mój pomiar z rastra, gdzie 1 mm to raptem 1,2 piksela.

## KRYTERIUM ROZJEMCY — zapisane PRZED pomiarem

Mierzę talerz z rastra instrukcji **inną metodą** niż poprzednio: nie obwiednią
wypełnionego kształtu, tylko profilem krawędzi po promieniu (ta sama metoda,
którą mierzyłem render — więc porównujemy metodą do metody, nie metodą do
metody innej).

* wynik **207,5 ±2 mm** → mój wcześniejszy pomiar był błędny, model wygrywa,
  **geometria idzie z modelu** (70 części, 58 w rozmiarze kontrolek);
* wynik **202,2 ±2 mm** → model odstaje mimo dobrych proporcji, geometria
  zostaje na rastrze;
* wynik pomiędzy albo poza obiema → **oba źródła niepewne**, geometria zostaje
  na rastrze i zapisujemy spór jako nierozstrzygnięty.

Trzeciego pomiaru tą samą metodą co pierwszy nie robię — powtórzyłby błąd.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

TU = pathlib.Path(__file__).resolve().parent
INSTRUKCJA = TU.parent / "2026-08-28_cdj3000" / "cdj3000_instrukcja.pdf"
STRONA = 14
SZEROKOSC_MM = 329.0
WYCINEK = (0.272, 0.258, 0.726, 0.694)      # ten sam co przy pierwszym pomiarze


def main() -> int:
    import pymupdf
    from PIL import Image

    d = pymupdf.open(INSTRUKCJA)
    pix = d[STRONA - 1].get_pixmap(dpi=1000)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    W, H = im.size
    im = im.crop((int(WYCINEK[0] * W), int(WYCINEK[1] * H),
                  int(WYCINEK[2] * W), int(WYCINEK[3] * H)))
    a = np.asarray(im).astype(float)
    atrament = a < 170

    xs = np.nonzero(atrament.any(axis=0))[0]
    ys = np.nonzero(atrament.any(axis=1))[0]
    px_mm = (xs.max() - xs.min() + 1) / SZEROKOSC_MM
    print(f"panel na rastrze: {xs.max() - xs.min() + 1} px = {SZEROKOSC_MM} mm "
          f"→ {px_mm:.3f} px/mm")

    # środek talerza: z pierwszego pomiaru wiadomo, że leży w okolicy
    # (163,6 · 296,5) mm od rogu panelu — szukamy dokładnego środka lokalnie,
    # maksymalizując symetrię profilu krawędzi
    gy, gx = np.gradient(a)
    krawedz = np.hypot(gx, gy)
    cx0 = xs.min() + 163.6 * px_mm
    cy0 = ys.min() + 296.5 * px_mm
    katy = np.linspace(0, 2 * np.pi, 1440, endpoint=False)
    promienie = np.arange(int(85 * px_mm), int(115 * px_mm))

    najlepszy = None
    for dx in np.arange(-3, 3.1, 1.0) * px_mm:
        for dy in np.arange(-3, 3.1, 1.0) * px_mm:
            cx, cy = cx0 + dx, cy0 + dy
            profil = []
            for r in promienie:
                px_ = np.clip((cx + r * np.cos(katy)).astype(int), 0, a.shape[1] - 1)
                py_ = np.clip((cy + r * np.sin(katy)).astype(int), 0, a.shape[0] - 1)
                profil.append(krawedz[py_, px_].mean())
            profil = np.array(profil)
            i = int(np.argmax(profil))
            if najlepszy is None or profil[i] > najlepszy[0]:
                najlepszy = (profil[i], promienie[i], cx, cy, profil.copy())

    sila, r_naj, cx, cy, profil = najlepszy
    srednica = 2 * r_naj / px_mm
    print(f"środek talerza: ({(cx - xs.min()) / px_mm:.1f}, "
          f"{(cy - ys.min()) / px_mm:.1f}) mm od rogu panelu")
    print("\nnajsilniejsze pierścienie w profilu krawędzi:")
    szczyty = [(promienie[i], profil[i]) for i in range(3, len(profil) - 3)
               if profil[i] == profil[max(0, i - 10): i + 11].max()]
    for r, s in sorted(szczyty, key=lambda t: -t[1])[:5]:
        print(f"   ⌀{2 * r / px_mm:6.1f} mm   siła {s:6.1f}")

    print(f"\nŚREDNICA Z RASTRA (profil krawędzi): {srednica:.1f} mm")
    for opis, wart in (("model 3D (siatka)", 207.4), ("model 3D (render)", 207.7),
                       ("mój pierwszy pomiar (obwiednia)", 202.2)):
        print(f"   wobec {opis:<32} {srednica - wart:+.1f} mm")

    if abs(srednica - 207.5) <= 2:
        werdykt = ("model wygrywa — mój pierwszy pomiar był błędny, "
                   "geometria może iść z modelu")
    elif abs(srednica - 202.2) <= 2:
        werdykt = "raster się potwierdza — geometria zostaje z instrukcji"
    else:
        werdykt = ("oba źródła niepewne — geometria zostaje z instrukcji, "
                   "spór zapisany jako nierozstrzygnięty")
    print(f"\nWERDYKT: {werdykt}")

    (TU / "rozjemca_talerz.json").write_text(json.dumps(
        {"srednica_z_rastra_mm": round(float(srednica), 1),
         "model_siatka": 207.4, "model_render": 207.7, "pierwszy_pomiar": 202.2,
         "px_na_mm": round(float(px_mm), 3), "werdykt": werdykt},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
