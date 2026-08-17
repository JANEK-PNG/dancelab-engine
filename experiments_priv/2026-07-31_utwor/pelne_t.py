"""Pełne T_(B→A): ręka kwantowana do ŻYWEJ siatki — odstępstwo od legendy.

Legenda Kordiego mówi: „energia A jest ściągana w stronę najbliższej
harmonicznej B". Dotąd czytaliśmy to najprościej: harmoniczne B to wieczna,
nieruchoma drabina wyliczona raz z akordu siatki. Ale pole B nie jest
nieruchome. Ten plik robi krok, którego legenda nie zapisała: cele
kwantyzacji są czytane per kolumna z FAKTYCZNYCH szczytów pola B w tej
chwili. Żywość celów ma tu DWA źródła (mówimy dokładnie, nie ładnie):
bramkę rubata (macierz gate_mat wmalowana w B) i Φ wlane w B przez
sprzężenie zwrotne w ostatniej tercji — pod koniec utworu rękę zaczyna
dyscyplinować także trzeci materiał. Zgięcie geometrii przez T_(A→B)
do celów NIE trafia: cele czytamy z pola B sprzed zgięcia (zgięta kopia
żyje w R_D, nie w polu). To świadoma granica tego eksperymentu.

Mechanika (jedna zmiana względem rubata — grupa kontrolna: rubato.wav):

  1. Cele: lokalne maksima slow(B, 1,2 s) per kolumna (pamięć, nie chwila —
     lekcja 2; bramka nie migocze w celach). Fallback: statyczna drabina
     tam, gdzie kolumna nie ma szczytów.
  2. Najbliższy cel: transformata odległości po osi f (per kolumna, w C).
  3. disp(f,t) = clip(cel − f, ±9 binów)·0,65 — te same widełki i ta sama
     siła co w legendzie; nowa jest wyłącznie ŻYWOŚĆ celu.
  4. Przejścia między celami wygładzone 0,45 s — portamento, nie skok.
  5. Przejmowanie bramki bez zmian: ×(0,5 + 0,5·gate_slow).

Wpięcie: podmiana hw.transform_BA (one_pass rozwiązuje nazwę w chwili
wywołania). Pole rubata, kompozycja, synteza — bit-identyczne z rubato.py,
bo importujemy rubato, które buduje wszystko przy imporcie. compose_A()
NIE jest wołane ponownie (drugie wywołanie = inny utwór).

Dowód (ADR-005, kod wspólny dla obu plików):
  szczyty audio 300–3000 Hz w sekcji sprzężenia (118–148 s), z wykluczeniem
  otoczenia statycznej drabiny; mediana odległości do celów żywych
  (z sidecara) kontra do drabiny — na pelne_t ma spaść, na rubato nie ma
  powodu być mała. Plus cała bateria ochronna rubata.
"""

from __future__ import annotations

import pathlib
import resource
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import distance_transform_edt
from scipy.signal import stft

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hybryda_wielorozdzielcza as hw                          # noqa: E402
import rubato as rb                                             # noqa: E402

DIR = pathlib.Path(__file__).resolve().parent
SR = hw.SR

# ── żywe cele kwantyzacji ──
PELNE_B: dict[str, np.ndarray] = {}       # aktualne pole B per płótno (na obrót)
PASS = 0                                   # 1/2 — który obrót wzoru trwa
ODSTEPSTWO: list[dict] = []                # metryki zamiaru z każdego wywołania
CELE_SRODKA: dict = {}                     # cele z obrotu 2 dla środka → sidecar


def _disp_statyczne(c):
    """Przesunięcia do wiecznej drabiny — dokładnie stara formuła (do metryki)."""
    if len(c.harm_bins) == 0:
        return np.zeros((c.NB, 1), np.float32)
    idx = np.arange(c.NB, dtype=np.float64)
    near = c.harm_bins[np.argmin(np.abs(idx[:, None] - c.harm_bins[None, :]),
                                 axis=1)]
    return (np.clip(near - idx, -9, 9)[:, None] * 0.65).astype(np.float32)


def _disp_zywe(c, B):
    """Przesunięcia do żywych celów + wiersze celów (do metryki i sidecara)."""
    Bs = hw.slow(B / (B.max() + 1e-9), 1.2, c)          # pamięć, nie chwila
    prog = 3e-3 * (Bs.max() + 1e-12)
    mask = np.zeros(Bs.shape, dtype=bool)
    mask[1:-1] = (Bs[1:-1] > Bs[:-2]) & (Bs[1:-1] > Bs[2:]) & (Bs[1:-1] > prog)
    has = mask.any(axis=0)
    if not has.all():                                    # fallback: legenda
        if len(c.harm_bins):
            hb = np.unique(np.clip(np.round(c.harm_bins).astype(int),
                                   0, c.NB - 1))
        else:
            hb = np.array([c.NB // 2])
        mask[np.ix_(hb, np.where(~has)[0])] = True
    ind = distance_transform_edt(~mask, sampling=[1.0, 1e6],
                                 return_distances=False, return_indices=True)
    near_rows = ind[0].astype(np.float32)                # indeksy < 2^15 — dokładne
    idx = np.arange(c.NB, dtype=np.float32)[:, None]
    disp = np.clip(near_rows - idx, -9, 9) * np.float32(0.65)
    disp = hw.slow(disp, 0.45, c)                        # portamento, nie skok
    assert np.isfinite(disp).all(), f"disp NaN na płótnie {c.name}"
    return disp, near_rows, mask


def transform_BA_zywe(c, A):
    """T_(B→A) z polem B zmiennym w czasie. Podmienia hw.transform_BA."""
    disp, near_rows, mask = _disp_zywe(c, PELNE_B[c.name])

    # metryka zamiaru: |cel żywy − cel z drabiny| w binach, ważone energią ręki
    if len(c.harm_bins):
        idx = np.arange(c.NB, dtype=np.float64)
        near_st = c.harm_bins[np.argmin(np.abs(idx[:, None]
                                               - c.harm_bins[None, :]), axis=1)]
    else:
        near_st = np.full(c.NB, c.NB / 2.0)
    dd = np.abs(near_rows - near_st[:, None].astype(np.float32))
    wagi = A
    sw = float(wagi.sum(dtype=np.float64)) + 1e-12
    ODSTEPSTWO.append(dict(
        plotno=c.name, obrot=PASS,
        sr_roznica_celow_binow=float((dd * wagi).sum(dtype=np.float64) / sw),
        udzial_odstepstwa=float((wagi * (dd > 1.0)).sum(dtype=np.float64) / sw)))
    if c.name == "srodek" and PASS == 2:
        rows, cols = np.where(mask)
        CELE_SRODKA["freq"] = c.bhz[rows].astype(np.float32)
        CELE_SRODKA["col"] = cols.astype(np.int32)
        CELE_SRODKA["tax"] = c.tax.astype(np.float32)
    quant = hw.warp(A, disp)
    return quant * (0.5 + 0.5 * c.gate_slow)[None, :]


hw.transform_BA = transform_BA_zywe        # one_pass czyta nazwę w chwili wywołania


# ── dowód RÓŻNICOWY: widmo pelne_t minus widmo rubata ──
# Kompozycja, pole rubata i synteza są identyczne — różni się WYŁĄCZNIE T.
# Więc energia, która się POJAWIŁA (diff > 0), to energia przesunięta przez
# nowe T i ma leżeć bliżej żywych celów; energia, która ZNIKŁA (diff < 0),
# opuściła okolice wiecznej drabiny. Wspólna treść (siatka, Φ, surowa ręka
# mA·A) kasuje się w różnicy — dowód nie jest samopotwierdzeniem.
LAT_LO, LAT_HI = 300.0, 3000.0
SEKCJA = (40.0, 148.0)                     # od wejścia C·R_D do wyciszenia
DF_S = 11.71875                            # Δf środka
DRABINA = np.array([f for f in hw.B_HARM_HZ
                    if LAT_LO - 1.5 * DF_S < f < LAT_HI + 1.5 * DF_S])


def _widmo(path):
    y, sr = sf.read(path, start=int(SEKCJA[0] * SR), stop=int(SEKCJA[1] * SR),
                    dtype="float64")
    m = y.mean(axis=1)
    f, t, Z = stft(m, SR, nperseg=8192, noverlap=8192 - 2048)
    sel = (f >= LAT_LO) & (f <= LAT_HI)
    return f[sel], t, np.abs(Z[sel])


def dowod_roznicowy(path_kontrola, path_pelne, cele):
    """Gdzie wylądowała energia przesunięta przez nowe T — i skąd wyszła."""
    fs_, t, Ma = _widmo(path_kontrola)
    _, _, Mb = _widmo(path_pelne)
    n = min(Ma.shape[1], Mb.shape[1])
    D = Mb[:, :n] - Ma[:, :n]
    prog = 0.03 * max(Ma.max(), Mb.max())
    tax, freq, col = cele["tax"], cele["freq"], cele["col"]
    ord_ = np.argsort(col, kind="stable")
    col_s, freq_s = col[ord_], freq[ord_]

    def strona(masksign):
        rr, cc = np.where(masksign)
        if len(rr) == 0:
            return dict(n=0, d_ziw=float("nan"), d_lat=float("nan"))
        wag = np.abs(D[rr, cc])
        ff = fs_[rr]
        tt = SEKCJA[0] + t[cc]
        jj = np.clip(np.round(tt / (tax[1] - tax[0])).astype(int),
                     0, len(tax) - 1)
        d_lat = np.abs(DRABINA[None, :] - ff[:, None]).min(axis=1)
        d_ziw = np.empty(len(ff))
        for k in range(len(ff)):
            lo, hi = np.searchsorted(col_s, [jj[k] - 2, jj[k] + 3])
            w = freq_s[lo:hi]
            d_ziw[k] = np.abs(w - ff[k]).min() if len(w) else np.nan
        ok = np.isfinite(d_ziw)

        def wmed(x, w):
            o = np.argsort(x)
            cw = np.cumsum(w[o])
            return float(x[o][np.searchsorted(cw, 0.5 * cw[-1])])

        return dict(n=int(ok.sum()), d_ziw=wmed(d_ziw[ok], wag[ok]),
                    d_lat=wmed(d_lat[ok], wag[ok]))

    return strona(D > prog), strona(D < -prog)


def main() -> int:
    global PASS
    print("pełne T_(B→A): cele kwantyzacji z pola B zmiennego w czasie")
    print(f"  pole rubata odziedziczone: |δ|max "
          f"{(np.abs(rb.D0).max() + rb.D1.max()) * 1000:.0f} ms · "
          f"hasz kompozycji {rb.HASH_A}")

    print("maluję (przez rubato: starty nut + macierz bramki)…", flush=True)
    przes = rb.paint_all_rubato(rb.EV)
    rb.sprawdz_przed_renderem(przes)

    # strażnik 1 — MECHANIKA na syntetycznym grzebieniu: jeden ząb przesunięty
    # w drugiej połowie; disp ma podążyć za nim (test celu, nie żywości)
    c = hw.CAN["srodek"]
    k0, dk = 150, 6
    B_syn = np.zeros_like(c.B)
    pol = c.cols // 2
    B_syn[k0, :pol] = 1.0
    B_syn[k0 + dk, pol:] = 1.0
    disp_s, _, _ = _disp_zywe(c, B_syn)
    w1 = float(np.median(disp_s[k0 + 3, : pol - int(3 / c.dt)]))
    w2 = float(np.median(disp_s[k0 + 3, pol + int(3 / c.dt):]))
    assert abs(w1 - (-3 * 0.65)) < 0.3 and abs(w2 - (3 * 0.65)) < 0.3, \
        f"mechanika celów nie podąża za B: {w1:.2f} / {w2:.2f}"
    print(f"  strażnik mechaniki: disp {w1:+.2f} → {w2:+.2f} binów "
          f"(zamiar −1,95 → +1,95) — cel podąża za B")

    # strażnik 2 — ŻYWOŚĆ na prawdziwych polach (dol informacyjnie: jego comby
    # to z konstrukcji dokładnie drabina, odstępstwo może przyjść tylko z Φ)
    PASS = 0
    for name in ("srodek", "gora", "dol"):
        cc = hw.CAN[name]
        PELNE_B[name] = cc.B
        _ = transform_BA_zywe(cc, cc.A)
        m0 = ODSTEPSTWO.pop()
        print(f"  żywość {name:7s}: |Δcelu| śr. {m0['sr_roznica_celow_binow']:.2f} "
              f"binów · odstępstwo na {m0['udzial_odstepstwa'] * 100:.0f}% energii ręki")
        if name in ("srodek", "gora"):
            assert m0["udzial_odstepstwa"] > 0.05, \
                f"żywe cele {name} nie różnią się od drabiny — odstępstwo jest atrapą"

    print("miary PRZED (kontrola = rubato.wav, ten sam kod)…", flush=True)
    przed = rb.raport_miar(DIR / "rubato.wav")

    fields0 = {n: (cc.A, cc.B) for n, cc in hw.CAN.items()}
    print("obrót 1 wzoru (T_(B→A) czyta żywe B)…", flush=True)
    PELNE_B.update({n: fields0[n][1] for n in fields0})
    PASS = 1
    pass1, _ = hw.one_pass(fields0)
    fields2 = {}
    for name, cc in hw.CAN.items():
        A, B = fields0[name]
        Phic = pass1[name][1]
        fb = cc.fb[None, :]
        fields2[name] = ((A + 0.35 * fb * Phic * A.max()).astype(np.float32),
                         (B + 0.25 * fb * Phic * B.max()).astype(np.float32))
    del pass1
    print("obrót 2 wzoru (B z wlanym Φ — trzeci materiał dyscyplinuje rękę)…",
          flush=True)
    PELNE_B.update({n: fields2[n][1] for n in fields2})
    PASS = 2
    pass2, _ = hw.one_pass(fields2)
    print(f"  RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30:.1f} GB",
          flush=True)

    gam_c = {n: np.interp(cc.tax, rb.T, rb.GAM).astype(np.float32)
             for n, cc in hw.CAN.items()}
    Ss = {n: pass2[n][0] * cc.intro[None, :] * gam_c[n][None, :]
          for n, cc in hw.CAN.items()}
    del pass2

    # baza torów z logu renderu rubato.wav (2026-08-04, zadanie b3fujn0sn):
    # "dol linii 84 · srodek 2091→2104 · gora 799" — kontrola, nie hybryda
    BAZA_TORY = {"dol": 84, "srodek": 2104, "gora": 799}
    Lm = np.zeros(hw.N_SAMP)
    Rm = np.zeros(hw.N_SAMP)
    for name, cc in hw.CAN.items():
        S = Ss[name]
        print(f"czytam partyturę płótna {name}…", flush=True)
        tracks = hw.track_partials(cc, S)
        Rr = hw.repaint(cc, tracks, S.shape)
        if name == "dol":
            N = np.maximum(S - 2.0 * hw.repaint(cc, tracks, S.shape, 6.0, 14), 0.0)
        else:
            N = np.maximum(S - Rr, 0.0)
        e_lin = float((np.minimum(Rr, S) ** 2).sum())
        e_pla = float((N ** 2).sum())
        fade = int(cc.fade_s * SR)
        porzucone = sum(
            1 for tr in tracks
            if min(int(tr["t"][-1] * cc.hop) + fade, hw.N_SAMP)
            - int(tr["t"][0] * cc.hop) < fade * 2)
        odch = (len(tracks) / BAZA_TORY[name] - 1) * 100
        print(f"  {name:7s} linii {len(tracks):5d} ({odch:+.0f}% od rubata) · "
              f"linie {e_lin / (e_lin + e_pla + 1e-9) * 100:3.0f}% · plamy "
              f"{e_pla / (e_lin + e_pla + 1e-9) * 100:3.0f}% · porzuconych "
              f"{porzucone}", flush=True)
        assert porzucone == 0, \
            "tor porzucony — żywe cele pofragmentowały partyturę"

        if name == "dol":
            pan_of = lambda tr, j: 0.0
        elif name == "gora":
            pan_of = lambda tr, j: 0.5 if j % 2 else -0.5
        else:
            A, B = fields2[name]
            An = A / (A.max() + 1e-9)
            Bn = B / (B.max() + 1e-9)
            pan_field = (-0.62 * cc.mA[None, :] * An + 0.62 * cc.mB[None, :] * Bn) \
                / (cc.mA[None, :] * An + cc.mB[None, :] * Bn + 0.35)

            def pan_of(tr, j, pf=pan_field, ccc=cc):
                return np.array([pf[min(max(int(ccc.bin_of(f)), 0), ccc.NB - 1), t]
                                 for f, t in zip(tr["f"], tr["t"])])

        Ls, Rs = hw.synth(cc, tracks, pan_of)
        xn = hw.noise_of(cc, N, seed=11)
        yn = xn if name == "dol" else hw.noise_of(cc, N, seed=12)
        s_rms = np.sqrt(((Ls + Rs) ** 2).mean()) + 1e-12
        n_rms = np.sqrt(((xn + yn) ** 2).mean()) + 1e-12
        gN = np.sqrt(e_pla / (e_lin + 1e-9)) * s_rms / n_rms
        Lm += Ls + gN * xn
        Rm += Rs + gN * yn

    mix = np.stack([Lm, Rm])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)

    np.savez_compressed(
        DIR / "pelne_t_zamiar.npz",
        cele_freq=CELE_SRODKA["freq"], cele_col=CELE_SRODKA["col"],
        cele_tax=CELE_SRODKA["tax"], drabina=DRABINA.astype(np.float32),
        odstepstwo=np.array([(m["sr_roznica_celow_binow"], m["udzial_odstepstwa"])
                             for m in ODSTEPSTWO], dtype=np.float64),
        hasz_A=np.str_(rb.HASH_A))
    y = mix.T.astype(np.float32)
    sf.write(DIR / "pelne_t.wav", y, SR, subtype="PCM_24")
    sf.write(DIR / "pelne_t.flac", y, SR, subtype="PCM_24")
    print("\nzapisane: pelne_t.wav / pelne_t.flac / pelne_t_zamiar.npz", flush=True)

    print("miary PO…", flush=True)
    po = rb.raport_miar(DIR / "pelne_t.wav")

    print("dowód różnicowy (widmo pelne_t minus widmo rubata)…", flush=True)
    poj, zni = dowod_roznicowy(DIR / "rubato.wav", DIR / "pelne_t.wav",
                               CELE_SRODKA)

    twarde_stopy = []
    wiersze = []

    def wiersz(nazwa, prz, poo, sukces, regres, stop=False):
        w = "OK" if sukces else ("REGRES" if regres else "uwaga")
        if stop and regres:
            twarde_stopy.append(nazwa)
        wiersze.append((nazwa, prz, poo, w))

    dosc = poj["n"] >= 5000 and zni["n"] >= 5000       # podłoga liczności:
    wiersz("dowód: energia POJAWIONA → żywy / drabina [Hz]",   # mało komórek =
           f"n={poj['n']}",                                     # uwaga, nie stop
           f"{poj['d_ziw']:.1f} / {poj['d_lat']:.1f}",
           dosc and poj["d_ziw"] < 0.75 * poj["d_lat"],
           dosc and poj["d_ziw"] > poj["d_lat"], stop=True)
    wiersz("dowód: energia ZNIKŁA → żywy / drabina [Hz]",
           f"n={zni['n']}",
           f"{zni['d_ziw']:.1f} / {zni['d_lat']:.1f} "
           "(znikać ma spod drabiny: drabina < żywy)",
           dosc and zni["d_lat"] < zni["d_ziw"], False)
    od2 = [m for m in ODSTEPSTWO if m["obrot"] == 2]
    wiersz("zamiar: odstępstwo od drabiny (obrót 2)", "—",
           " · ".join(f"{m['plotno']} {m['udzial_odstepstwa'] * 100:.0f}%"
                      for m in od2),
           all(m["udzial_odstepstwa"] > 0.05 for m in od2
               if m["plotno"] in ("srodek", "gora")), False)

    # czystość: twardy stop tylko na oknach ≤ 100 s — tam cele ≈ drabina,
    # więc spadek byłby artefaktem; okna późne (Φ w celach) raportowane osobno
    pur_wcz = [p for p, t0 in zip(po["purity"], rb.OKNA_PURITY) if t0 <= 100]
    pur_poz = [p for p, t0 in zip(po["purity"], rb.OKNA_PURITY) if t0 > 100]
    wiersz("czystość okna ≤100 s: mediana / min [dB]",
           f"{przed['purity_med']:+.1f} (całość)",
           f"{np.median(pur_wcz):+.1f} / {np.min(pur_wcz):+.1f}",
           np.median(pur_wcz) >= 7.5 and np.min(pur_wcz) >= -1.5,
           np.median(pur_wcz) < 5.0 or np.min(pur_wcz) < -3.0, stop=True)
    wiersz("czystość okna >100 s (żywe cele legalnie ruszają nuty)",
           "—", f"{np.median(pur_poz):+.1f} / {np.min(pur_poz):+.1f}",
           np.min(pur_poz) >= -5.0, False)
    spadki = sum(1 for a, b in zip(po["takt_puls_okna"], przed["takt_puls_okna"])
                 if a < b - 4.0)
    wiersz("puls w czasie taktu [dB]", f"{przed['takt_puls']:+.1f}",
           f"{po['takt_puls']:+.1f} (okien poniżej −4: {spadki})",
           po["takt_puls"] >= przed["takt_puls"] - 1.0 and spadki <= 1,
           po["takt_puls"] < przed["takt_puls"] - 2.0, stop=True)
    skoki = [(k, a - b) for k, (a, b) in
             enumerate(zip(po["hf_sekcje"], przed["hf_sekcje"])) if a - b > 10]
    wiersz("energia 46–48 kHz per sekcja", "baza rubata",
           "bez skoków" if not skoki else
           "; ".join(f"sekcja {k}: {d:+.0f} dB" for k, d in skoki),
           not skoki, bool(skoki), stop=True)

    os1k = np.arange(len(po["d_air"])) / 1000.0
    w = slice(rb.BRZEG, len(po["d_air"]) - rb.BRZEG)
    x = rb.detr_lin(np.interp(os1k, rb.T, rb.D0)[w])
    yv = rb.detr_lin(po["d_air"][w])
    nach = float(np.polyfit(x, yv, 1)[0])
    rkor = float(np.corrcoef(x, yv)[0, 1])
    wiersz("pole rubata dalej brzmi (nachylenie / r)",
           "1.16 / +0.79", f"{nach:.2f} / {rkor:+.2f}",
           rkor >= 0.55 and 0.35 <= nach <= 1.25, rkor < 0.30)
    wiersz("rozjazd rejestrów [ms]", f"{przed['rozjazd_ms']:+.1f}",
           f"{po['rozjazd_ms']:+.1f}",
           abs(po["rozjazd_ms"] - przed["rozjazd_ms"]) < 25,
           abs(po["rozjazd_ms"] - przed["rozjazd_ms"]) > 45)
    wiersz("korelacja L/R środek", f"{przed['corr_220_6000']:.3f}",
           f"{po['corr_220_6000']:.3f}",
           0.70 <= po["corr_220_6000"] <= 0.97,
           po["corr_220_6000"] > 0.99 or po["corr_220_6000"] < 0.65)
    wiersz("fuzja zespołu harmonicznego", f"{przed['fuzja_nuty']:.3f}",
           f"{po['fuzja_nuty']:.3f}",
           po["fuzja_nuty"] >= 0.45, po["fuzja_nuty"] < 0.40)
    wiersz("crest dołu 60–130 s [dB]", f"{przed['crest']:.1f}", f"{po['crest']:.1f}",
           po["crest"] <= przed["crest"] + 1.0, po["crest"] > przed["crest"] + 3.0)
    wiersz("szczyt / skończoność", f"{przed['szczyt']:.4f}",
           f"{po['szczyt']:.4f} / {po['skonczony']}",
           abs(po["szczyt"] - 0.89) < 1e-4 and po["skonczony"],
           not (abs(po["szczyt"] - 0.89) < 1e-4 and po["skonczony"]))

    print("\n" + "=" * 88)
    print(f"{'miara':46s} {'PRZED (rubato)':>18s} → PO (pelne_t)")
    print("-" * 88)
    for nazwa, prz, poo, wer in wiersze:
        print(f"[{wer:6s}] {nazwa:46s} {prz:>18s} → {poo}")
    print("=" * 88)

    # obraz: trzy płótna + żywe cele kontra drabina w sekcji sprzężenia
    mch = y.mean(axis=1).astype(np.float64)
    fig, axes = plt.subplots(4, 1, figsize=(14, 13), facecolor=hw.PAPER,
                             gridspec_kw={"hspace": 0.34},
                             height_ratios=[1.2, 1, 0.8, 0.9])
    plans = [("gora", 1024, 6000, 46000, axes[0]),
             ("srodek", 8192, 220, 6000, axes[1]),
             ("dol", 32768, 20, 220, axes[2])]
    for name, nper, lo, hi, ax in plans:
        f, t, Z = stft(mch, SR, nperseg=nper, noverlap=int(nper * 0.75))
        Sd = 20 * np.log10(np.abs(Z) + 1e-10)
        k = (f >= lo) & (f <= hi)
        top = Sd[k].max()
        ax.pcolormesh(t, f[k], np.clip(Sd[k], top - 66, top),
                      shading="gouraud", cmap="magma", rasterized=True)
        ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        ax.set_title(f"{name.upper()}  {lo}–{hi} Hz", color=hw.INK, fontsize=10,
                     loc="left", pad=6, family="monospace")
        ax.set_facecolor(hw.PAPER)
        for sp in ax.spines.values():
            sp.set_color(hw.INK)
        ax.tick_params(colors=hw.INK, labelsize=8)
    ax = axes[3]
    tax, freq, col = (CELE_SRODKA["tax"], CELE_SRODKA["freq"],
                      CELE_SRODKA["col"])
    okno = (tax[col] >= 100) & (tax[col] <= 160) & (freq >= 300) & (freq <= 2000)
    ax.scatter(tax[col][okno][::7], freq[okno][::7], s=0.5, c="#3a6ea5",
               alpha=0.5, label="cele żywe (szczyty B w tej chwili)")
    for fh in DRABINA[DRABINA < 2000]:
        ax.axhline(fh, color=hw.ACC, lw=0.7, ls="--", alpha=0.8)
    ax.axhline(-1, color=hw.ACC, lw=0.7, ls="--", label="wieczna drabina (legenda)")
    ax.axvline(112, color=hw.INK, lw=0.6, ls=":")
    ax.text(112.5, 1850, "Φ→B: trzeci materiał\nwchodzi w cele",
            color=hw.INK, fontsize=8, family="monospace")
    ax.set_yscale("log")
    ax.set_ylim(300, 2000)
    ax.set_xlim(100, 160)
    ax.set_xlabel("czas [s]", color=hw.INK, fontsize=9)
    ax.set_ylabel("częstotliwość [Hz]", color=hw.INK, fontsize=9)
    ax.set_title("PEŁNE T_(B→A): kwantyzacja do żywej siatki — cele kontra legenda",
                 color=hw.INK, fontsize=10, loc="left", pad=6, family="monospace")
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    ax.set_facecolor(hw.PAPER)
    for sp in ax.spines.values():
        sp.set_color(hw.INK)
    ax.tick_params(colors=hw.INK, labelsize=8)
    fig.suptitle("PEŁNE T_(B→A) — ręka ściągana tam, gdzie siatka JEST, "
                 "nie gdzie była na początku", color=hw.INK, fontsize=12,
                 family="monospace", x=0.123, ha="left")
    fig.savefig(DIR / "pelne_t.png", dpi=150, facecolor=hw.PAPER,
                bbox_inches="tight")
    print(f"{DIR / 'pelne_t.png'}")

    if twarde_stopy:
        print(f"\nTWARDY STOP: {', '.join(twarde_stopy)} — plik zostaje do "
              "odsłuchu, ale render jest ODRZUCONY.")
        raise SystemExit(1)
    print("\nwerdykt: render zdrowy, odstępstwo w OBRAZIE potwierdzone "
          "(strażnicy). Czy dociera do DŹWIĘKU — rozstrzyga osobno "
          "pelne_t_dowod.py (miara przewidziane-kontra-zmierzone; wynik "
          "z 2026-08-04: przy parametrach legendy NIE dociera — ginie "
          "pod podłogą chaosu renderów).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
