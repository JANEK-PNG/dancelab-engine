"""Rendery referencyjne z modelu 3D — materiał, detal i (być może) geometria.

    blender --background --python experiments_priv/2026-08-29_model_3d/rendery.py

## Co już wiadomo

`z_fbx.py` rozstrzygnął zapisane wcześniej kryterium: **model to cztery zlepione
bryły** (kable, DJM-A9, dwa CDJ), a nie osobne kontrolki. Geometrii per kontrolka
z obwiedni obiektów nie będzie — tak było zapisane i tak zostaje.

Wyszło natomiast coś, czego nie przewidziałem: model jest **wierny w proporcjach**.
Po jednym wspólnym współczynniku (7,330 wzięty z szerokości) głębokość wychodzi
454,1 mm wobec zmierzonych 453,0 — różnica **0,25%**. Wysokość odstaje o 17%, ale
obwiednia liczy gałki, talerz i suwak, więc do rzutu Z GÓRY to nie ma znaczenia.

## NOWE KRYTERIUM — zapisane PRZED użyciem renderu do geometrii

Render ortograficzny z góry daje ~12 px/mm, czyli dziesięć razy więcej niż raster
z instrukcji (1,2 px/mm). Ale to nadal jest pomiar z obrazu, więc musi się
wylegitymować **na wielkościach zmierzonych niezależnie z instrukcji**:

| co | z instrukcji | tolerancja |
|---|---|---|
| talerz jog | ⌀ 202,2 mm | ±2 mm |
| ekran z ramką | 199,5 × 108,8 mm | ±2 mm |
| listwa ośmiu padów | 268,5 × 18,8 mm | ±2 mm |

**Wszystkie trzy muszą się zmieścić.** Wtedy — i tylko wtedy — wolno z tego
renderu odczytywać pozycje pozostałych kontrolek. Jeśli choć jedna wypadnie poza,
render zostaje źródłem materiału i detalu, a geometria zostaje na rastrze ±1 mm.

Sprawdzenie robi osobny skrypt (`zmierz_render.py`), już po renderze — żeby nie
dało się dopasować renderu do oczekiwanego wyniku.

## Czego ten skrypt nie robi

Nie publikuje renderów i nie kopiuje tekstur do repozytorium (katalog jest w
`.gitignore`). Model jest cudzy i służy jako referencja do narysowania własnego
SVG. Mikser to DJM-A9, nie DJM-900NXS2 — materiał tak, geometria nigdy.
"""

import json
import math
import pathlib
import sys

import bpy
import mathutils

TU = pathlib.Path(__file__).resolve().parent
FBX = TU / "source" / "Pioneer CDJ 3000, Pioneer DJM A9.fbx"
RENDER = TU / "render"
SZEROKOSC_CDJ_MM = 329.0
PIKSELI_NA_MM = 12.0


def obwiednia(ob):
    mini = mathutils.Vector((1e18,) * 3)
    maxi = mathutils.Vector((-1e18,) * 3)
    for rog in ob.bound_box:
        p = ob.matrix_world @ mathutils.Vector(rog)
        mini = mathutils.Vector(map(min, mini, p))
        maxi = mathutils.Vector(map(max, maxi, p))
    return mini, maxi


def swiatlo(nazwa, loc, energia, rozmiar):
    dane = bpy.data.lights.new(nazwa, type="AREA")
    dane.energy = energia
    dane.size = rozmiar
    ob = bpy.data.objects.new(nazwa, dane)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (0, 0, 0)
    return ob


def kamera_z_gory(mini, maxi, margines=1.02):
    """Ortograficzna, patrząca wzdłuż osi o NAJMNIEJSZYM rozmiarze.

    Pierwsza wersja zakładała, że wysokość to Y — i wyrenderowała pusty kadr,
    bo w tym pliku wysokością jest Z. Oś wybieramy więc z danych: płyta jest
    płaska, więc oś najcieńsza to ta, wzdłuż której się na nią patrzy.
    """
    rozmiar = maxi - mini
    os_h = min(range(3), key=lambda i: rozmiar[i])       # oś „w dół"
    plaskie = [i for i in range(3) if i != os_h]
    srodek = (mini + maxi) / 2

    dane = bpy.data.cameras.new("kamera")
    dane.type = "ORTHO"
    dane.ortho_scale = max(rozmiar[i] for i in plaskie) * margines
    ob = bpy.data.objects.new("kamera", dane)
    bpy.context.collection.objects.link(ob)

    poz = list(srodek)
    poz[os_h] = maxi[os_h] + rozmiar[os_h] * 10 + 1.0
    ob.location = poz
    # patrzenie w ujemną stronę osi os_h
    kierunek = mathutils.Vector((0.0, 0.0, 0.0))
    kierunek[os_h] = -1.0
    ob.rotation_euler = kierunek.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    print(f"  oś patrzenia: {'XYZ'[os_h]} · kadr {rozmiar[plaskie[0]]:.2f} × "
          f"{rozmiar[plaskie[1]]:.2f} jednostek")
    return ob, rozmiar[plaskie[0]], rozmiar[plaskie[1]]


def ustaw_render(px_x: int, px_y: int) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"   # w Blenderze 5.2 EEVEE Next nazywa się po prostu EEVEE
    sc.render.resolution_x = px_x
    sc.render.resolution_y = px_y
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("swiat")
    sc.world.use_nodes = True
    tlo = sc.world.node_tree.nodes["Background"]
    tlo.inputs[0].default_value = (0.05, 0.055, 0.065, 1.0)
    tlo.inputs[1].default_value = 1.2


def zapisz(nazwa: str) -> None:
    RENDER.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(RENDER / nazwa)
    bpy.ops.render.render(write_still=True)
    print(f"  → {nazwa}")


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX))

    obiekty = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    cdj = obiekty.get("Pioneer CDJ 3000 NXS 1")
    djm = obiekty.get("Pioneer DJM A9")
    kable = obiekty.get("Cables")
    if cdj is None:
        print("BŁĄD: nie znalazłem obiektu CDJ")
        return 2
    if kable:
        kable.hide_render = True          # kable zasłaniają panel z góry

    mini, maxi = obwiednia(cdj)
    skala_mm = SZEROKOSC_CDJ_MM / (maxi.x - mini.x)
    print(f"skala modelu: 1 jednostka = {skala_mm:.4f} mm")

    for nazwa in ("Pioneer CDJ 3000 NXS 2", "Pioneer DJM A9"):
        if nazwa in obiekty:
            obiekty[nazwa].hide_render = True

    swiatlo("gorne", (mini.x, maxi.y * 3, mini.z), 4000, (maxi.x - mini.x) * 2)
    swiatlo("boczne", (maxi.x * 2, maxi.y * 2, maxi.z), 1500,
            (maxi.x - mini.x))

    # 1) rzut ortograficzny z góry — kandydat na źródło geometrii
    _, szer, glab = kamera_z_gory(mini, maxi)
    px_x = int(SZEROKOSC_CDJ_MM * PIKSELI_NA_MM)
    px_y = int(px_x * (glab / szer))
    ustaw_render(px_x, px_y)
    print(f"\nrzut z góry: {px_x} × {px_y} px "
          f"({PIKSELI_NA_MM:.0f} px/mm przy szerokości {SZEROKOSC_CDJ_MM:.0f} mm)")
    zapisz("cdj_z_gory_orto.png")

    (TU / "render_meta.json").write_text(json.dumps({
        "plik": "cdj_z_gory_orto.png",
        "px_na_mm": PIKSELI_NA_MM,
        "szerokosc_kadru_mm": round(max(szer, glab) * skala_mm * 1.02, 2),
        "szerokosc_cdj_mm": SZEROKOSC_CDJ_MM,
        "uwaga": ("Kadr jest kwadratowy w największym wymiarze i ma 2% marginesu; "
                  "px/mm liczyć z rzeczywistej obwiedni panelu na obrazie, nie "
                  "z tej liczby.")}, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2) widoki poglądowe — materiał i detal, nie pomiar
    kam = bpy.context.scene.camera
    srodek = (mini + maxi) / 2
    przekatna = (maxi - mini).length
    ujecia = {
        "cdj_perspektywa.png": (35, (1.0, 0.75, 1.0)),
        "cdj_przod.png":       (35, (0.0, 0.18, 1.35)),
        "cdj_bok.png":         (35, (1.35, 0.18, 0.0)),
        "cdj_talerz.png":      (60, (0.35, 0.55, 0.35)),
        "cdj_ekran.png":       (60, (-0.3, 0.6, 0.45)),
    }
    ustaw_render(1800, 1350)
    kam.data.type = "PERSP"
    for nazwa, (ogniskowa, kier) in ujecia.items():
        kam.data.lens = ogniskowa
        v = mathutils.Vector(kier).normalized()
        kam.location = srodek + v * przekatna * 1.1
        kier_do = (srodek - kam.location).normalized()
        kam.rotation_euler = kier_do.to_track_quat("-Z", "Y").to_euler()
        zapisz(nazwa)

    # 3) cały zestaw: dwa CDJ i mikser
    for nazwa in ("Pioneer CDJ 3000 NXS 2", "Pioneer DJM A9"):
        if nazwa in obiekty:
            obiekty[nazwa].hide_render = False
    wszystkie = [o for o in obiekty.values() if o is not kable]
    mini2 = mathutils.Vector((1e18,) * 3)
    maxi2 = mathutils.Vector((-1e18,) * 3)
    for o in wszystkie:
        a, b = obwiednia(o)
        mini2 = mathutils.Vector(map(min, mini2, a))
        maxi2 = mathutils.Vector(map(max, maxi2, b))
    srodek2 = (mini2 + maxi2) / 2
    przek2 = (maxi2 - mini2).length
    for nazwa, kier in (("zestaw_z_gory.png", (0.0, 1.0, 0.001)),
                        ("zestaw_perspektywa.png", (0.6, 0.8, 1.0)),
                        ("zestaw_przod.png", (0.0, 0.25, 1.3))):
        v = mathutils.Vector(kier).normalized()
        kam.location = srodek2 + v * przek2 * 0.95
        kam.rotation_euler = (srodek2 - kam.location).normalized() \
            .to_track_quat("-Z", "Y").to_euler()
        zapisz(nazwa)

    if djm:
        kam.data.lens = 60
        a, b = obwiednia(djm)
        s = (a + b) / 2
        kam.location = s + mathutils.Vector((0.2, 1.0, 0.35)).normalized() * (b - a).length * 0.8
        kam.rotation_euler = (s - kam.location).normalized().to_track_quat("-Z", "Y").to_euler()
        zapisz("djm_a9_detal.png")

    print(f"\nrendery w: {RENDER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
