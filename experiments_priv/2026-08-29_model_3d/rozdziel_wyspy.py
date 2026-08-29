"""Czy zlepiona bryła da się rozdzielić na kontrolki. Test, nie założenie.

    blender --background --python experiments_priv/2026-08-29_model_3d/rozdziel_wyspy.py

## Skąd ten test

Kryterium 1 z `z_fbx.py` brzmiało: „kontrolki muszą być osobnymi OBIEKTAMI,
próg 30" — i odpadło, bo każde urządzenie to jeden obiekt. Ale obiekt w Blenderze
może zawierać wiele **rozłącznych wysp geometrii**, a `Separate by Loose Parts`
rozbija je na osobne obiekty. To jest ten sam test co poprzednio (czy kontrolki
są rozdzielne), tylko zrobiony właściwym narzędziem.

## KRYTERIUM — zapisane PRZED uruchomieniem

Geometria z modelu wchodzi do gry tylko wtedy, gdy spełnione są OBA warunki:

1. **Liczba części.** CDJ-3000 ma ~50 kontrolek plus obudowa, ekran i talerz.
   Próg: rozdzielenie musi dać co najmniej **60 części** dla jednego CDJ-a.
   Mniej = model jest zlepiony na poziomie siatki i geometrii z niego nie ma.
2. **Trafienie w znane wymiary.** Wśród części musi znaleźć się talerz o
   średnicy **202 ±3 mm** (mierzone jako większy z dwóch poziomych wymiarów
   obwiedni). To jest wielkość zmierzona niezależnie z instrukcji; jeśli jej
   tam nie ma, rozdzielenie może i zadziałało, ale nie wiadomo na co patrzymy.

Wynik przeciwny którejkolwiek pozycji zostawia werdykt z `WERDYKT.md` bez zmian:
geometria z rastra ±1 mm, model jako materiał.

Skala: 1 jednostka modelu = 136,4219 mm (z szerokości CDJ = 329 mm, ustalone
w `z_fbx.py`).
"""

import json
import pathlib
import sys

import bpy

TU = pathlib.Path(__file__).resolve().parent
FBX = TU / "source" / "Pioneer CDJ 3000, Pioneer DJM A9.fbx"
CDJ = "Pioneer CDJ 3000 NXS 1"
SZEROKOSC_CDJ_MM = 329.0
PROG_CZESCI = 60
TALERZ_MM, TALERZ_TOL = 202.0, 3.0


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX))

    cdj = bpy.data.objects.get(CDJ)
    if cdj is None:
        print(f"BŁĄD: brak obiektu {CDJ}")
        return 2

    for o in list(bpy.data.objects):
        if o is not cdj:
            bpy.data.objects.remove(o, do_unlink=True)

    skala_mm = SZEROKOSC_CDJ_MM / cdj.dimensions.x
    print(f"skala: 1 jednostka = {skala_mm:.4f} mm")
    print(f"przed rozdzieleniem: 1 obiekt, {len(cdj.data.vertices)} wierzchołków")

    bpy.context.view_layer.objects.active = cdj
    cdj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")

    czesci = [o for o in bpy.data.objects if o.type == "MESH"]
    print(f"po rozdzieleniu: {len(czesci)} części")

    spis = []
    for o in czesci:
        d = o.dimensions
        spis.append({
            "nazwa": o.name,
            "wymiary_mm": [round(d.x * skala_mm, 1), round(d.y * skala_mm, 1),
                           round(d.z * skala_mm, 1)],
            "srodek_mm": [round(v * skala_mm, 1) for v in o.matrix_world.translation],
            "wierzcholkow": len(o.data.vertices),
        })
    spis.sort(key=lambda s: -max(s["wymiary_mm"]))

    print("\npiętnaście największych części:")
    for s in spis[:15]:
        w = s["wymiary_mm"]
        print(f"  {w[0]:>7.1f} × {w[1]:>7.1f} × {w[2]:>6.1f} mm   "
              f"{s['wierzcholkow']:>6} wierzch.  {s['nazwa'][:34]}")

    # rozkład wielkości — kontrolki to rzeczy rzędu 5–60 mm
    kontrolki = [s for s in spis
                 if 4.0 <= max(s["wymiary_mm"][0], s["wymiary_mm"][1]) <= 60.0]
    print(f"\nczęści o rozmiarze kontrolki (4–60 mm w rzucie): {len(kontrolki)}")

    kandydaci_talerz = [s for s in spis
                        if abs(max(s["wymiary_mm"][0], s["wymiary_mm"][1])
                               - TALERZ_MM) <= TALERZ_TOL]
    print(f"części pasujące na talerz ⌀{TALERZ_MM:.0f} ±{TALERZ_TOL:.0f} mm: "
          f"{len(kandydaci_talerz)}")
    for s in kandydaci_talerz[:4]:
        print(f"   {s['wymiary_mm']} mm — {s['nazwa'][:40]}")

    k1 = len(czesci) >= PROG_CZESCI
    k2 = bool(kandydaci_talerz)
    print(f"\nKRYTERIUM 1 (≥{PROG_CZESCI} części): "
          f"{'SPEŁNIONE' if k1 else 'NIESPEŁNIONE'} ({len(czesci)})")
    print(f"KRYTERIUM 2 (talerz ⌀{TALERZ_MM:.0f} ±{TALERZ_TOL:.0f}): "
          f"{'SPEŁNIONE' if k2 else 'NIESPEŁNIONE'}")
    print("\nWERDYKT: " + ("geometria z modelu jest dostępna"
                           if k1 and k2 else
                           "werdykt z WERDYKT.md bez zmian — geometria z rastra"))

    (TU / "czesci.json").write_text(json.dumps(
        {"skala_mm_na_jednostke": round(skala_mm, 4),
         "czesci": len(czesci), "prog": PROG_CZESCI,
         "kryterium_1": k1, "kryterium_2": k2,
         "spis": spis}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"spis części → {TU / 'czesci.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
