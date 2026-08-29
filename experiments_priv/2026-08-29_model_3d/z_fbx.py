"""Model 3D CDJ-3000 → geometria i materiał. Uruchamiany przez Blendera.

    blender --background --python experiments_priv/2026-08-29_model_3d/z_fbx.py

## Po co

Rysunek CDJ-3000 w instrukcji to jeden obrazek rastrowy — cały zadruk strony ma
897 px szerokości, czyli panel ma najwyżej **1,2 piksela na milimetr**. Duże
elementy (talerz, ekran, listwa padów) z tego wychodzą, pozycje małych
przycisków nie. Model 3D może to rozstrzygnąć albo nie — i o tym jest kryterium
niżej.

## KRYTERIUM PRZERWANIA — zapisane PRZED uruchomieniem

Model daje geometrię tylko wtedy, gdy spełni oba warunki:

1. **Rozdzielność.** Kontrolki muszą być osobnymi obiektami. Próg: co najmniej
   **30 obiektów siatkowych** przypadających na sam CDJ. Jedna zlepiona siatka
   albo kilka brył = geometria zostaje z rastra (±1 mm, jawnie oznaczona),
   a model służy wyłącznie do materiału i renderów.
2. **Skala.** Obwiednia CDJ musi wyjść **329 × 453 mm ±3 mm**, a talerz
   **⌀202 ±2 mm** — to są liczby zmierzone niezależnie, z instrukcji. Rozjazd
   większy znaczy, że model nie jest w skali; wtedy wolno go użyć do proporcji
   względnych, ale nie do milimetrów.

Wynik przeciwny kryterium NIE jest porażką eksperymentu — jest odpowiedzią.
Zapisujemy go i wracamy do rastra.

## Czego ten skrypt nie robi

Nie kopiuje tekstur do repozytorium i nie publikuje renderów. Model jest cudzy
i służy wyłącznie jako referencja do narysowania własnego SVG.
Mikser w pliku to **DJM-A9, nie DJM-900NXS2** — inny sprzęt tej samej rodziny.
Z niego bierzemy materiał, nigdy geometrię.
"""

import json
import pathlib
import sys

import bpy

TU = pathlib.Path(bpy.path.abspath("//")) if bpy.data.filepath else \
    pathlib.Path(__file__).resolve().parent
FBX = TU / "source" / "Pioneer CDJ 3000, Pioneer DJM A9.fbx"
RENDER = TU / "render"
PROG_OBIEKTOW = 30
PANEL_MM = (329.0, 453.0)
TALERZ_MM = 202.0


def czysta_scena() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def wymiary_mm(ob) -> tuple[float, float, float]:
    """Wymiary obiektu w milimetrach, z uwzględnieniem skali sceny."""
    s = bpy.context.scene.unit_settings.scale_length or 1.0
    return tuple(round(w * s * 1000.0, 1) for w in ob.dimensions)


def main() -> int:
    if not FBX.exists():
        print(f"BŁĄD: nie ma pliku {FBX}")
        return 2

    czysta_scena()
    print(f"importuję {FBX.name} …")
    bpy.ops.import_scene.fbx(filepath=str(FBX))

    siatki = [o for o in bpy.data.objects if o.type == "MESH"]
    print(f"\nobiektów siatkowych: {len(siatki)}")
    print(f"materiałów: {len(bpy.data.materials)} · obrazów: {len(bpy.data.images)}")

    # obwiednia całej sceny — z niej dopiero widać, czy model jest w skali
    import mathutils
    mini = mathutils.Vector((1e9, 1e9, 1e9))
    maxi = mathutils.Vector((-1e9, -1e9, -1e9))
    for o in siatki:
        for rog in o.bound_box:
            p = o.matrix_world @ mathutils.Vector(rog)
            mini = mathutils.Vector(map(min, mini, p))
            maxi = mathutils.Vector(map(max, maxi, p))
    rozmiar = (maxi - mini) * (bpy.context.scene.unit_settings.scale_length or 1.0)
    print(f"cała scena: {rozmiar.x * 1000:.0f} × {rozmiar.y * 1000:.0f} × "
          f"{rozmiar.z * 1000:.0f} mm")

    spis = []
    for o in sorted(siatki, key=lambda o: -o.dimensions.length):
        w = wymiary_mm(o)
        loc = tuple(round(v * 1000, 1) for v in o.matrix_world.translation)
        spis.append({"nazwa": o.name, "wymiary_mm": w, "srodek_mm": loc,
                     "wierzcholkow": len(o.data.vertices),
                     "materialy": [m.name for m in o.data.materials if m]})
    print("\ndwadzieścia największych obiektów:")
    for s in spis[:20]:
        print(f"  {s['nazwa'][:44]:<44} {s['wymiary_mm']} mm  "
              f"({s['wierzcholkow']} wierzch.)")

    (TU / "obiekty.json").write_text(
        json.dumps({"plik": FBX.name,
                    "scena_mm": [round(rozmiar.x * 1000, 1),
                                 round(rozmiar.y * 1000, 1),
                                 round(rozmiar.z * 1000, 1)],
                    "obiektow": len(siatki),
                    "prog_kryterium": PROG_OBIEKTOW,
                    "obiekty": spis}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    print(f"\nKRYTERIUM 1 (rozdzielność, próg {PROG_OBIEKTOW} obiektów): "
          f"{'SPEŁNIONE' if len(siatki) >= PROG_OBIEKTOW else 'NIESPEŁNIONE'}")
    print("KRYTERIUM 2 (skala) — do sprawdzenia po wskazaniu, który obiekt to CDJ; "
          f"szukamy panelu {PANEL_MM[0]:.0f} × {PANEL_MM[1]:.0f} mm ±3 "
          f"i talerza ⌀{TALERZ_MM:.0f} ±2")
    print(f"\nspis obiektów → {TU / 'obiekty.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
