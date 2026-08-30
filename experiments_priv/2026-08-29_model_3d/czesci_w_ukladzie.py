"""70 części modelu → współrzędne w układzie panelu + ponumerowany podgląd.

    blender --background --python .../czesci_w_ukladzie.py

Rozdzielenie po wyspach geometrii (`rozdziel_wyspy.py`) dało 70 części, z czego
58 w rozmiarze kontrolki. Ten skrypt przelicza je na układ panelu widziany
Z GÓRY — czyli dokładnie ten, w którym rysujemy model konsoli — i wypisuje
w milimetrach od lewego górnego rogu obudowy.

Osie: w układzie ŚWIATA (a nie obiektu, bo import FBX obraca scenę) jest
**X = szerokość, Y = głębokość, Z = wysokość**. Sprawdzone pomiarem: gałki
wychodzą 15,6 mm w X, 15,6 mm w Y i 2,8 mm w Z — czyli okrągłe i płaskie,
a nie okrągłe i wysokie. Pierwsza wersja tego skryptu brała Z za głębokość
i wszystkie części wylądowały w jednym pasie na wysokości 94 mm.

**Zwrot osi Y też trzeba odwrócić** i to złapał Janek patrząc na podgląd:
w modelu Y rośnie ku TYŁOWI urządzenia, a na rysunku panelu y rośnie w DÓŁ,
czyli ku przedniej krawędzi. Bez odwrócenia talerz (207 × 207 mm) lądował
u góry, ekran (232 × 155 mm) na dole, a rząd sześciu przycisków SOURCE /
BROWSE / TAG LIST / PLAYLIST / SEARCH / MENU — który na sprzęcie jest
najwyżej — wychodził przy przedniej krawędzi.

## Do czego to służy, a do czego nie

Rozjemca talerza rozstrzygnął, że **wymiary bezwzględne bierzemy z instrukcji**
(talerz 203,6 mm z rastra wobec 207,4 z modelu). Model daje natomiast to, czego
raster przy 1,2 px/mm dać nie może: **pozycje wszystkich drobnych kontrolek**.
Dlatego wynik jest oznaczony jako `zrodlo: "model 3D (pozycja)"` — pozycja
z modelu, wymiar do potwierdzenia.
"""

import json
import pathlib
import sys

import bpy

TU = pathlib.Path(__file__).resolve().parent
FBX = TU / "source" / "Pioneer CDJ 3000, Pioneer DJM A9.fbx"
CDJ = "Pioneer CDJ 3000 NXS 1"
SZEROKOSC_MM = 329.0


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX))
    cdj = bpy.data.objects.get(CDJ)
    if cdj is None:
        print(f"BŁĄD: brak {CDJ}")
        return 2
    for o in list(bpy.data.objects):
        if o is not cdj:
            bpy.data.objects.remove(o, do_unlink=True)

    skala = SZEROKOSC_MM / cdj.dimensions.x
    bpy.context.view_layer.objects.active = cdj
    cdj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    czesci = [o for o in bpy.data.objects if o.type == "MESH"]

    import mathutils

    def obw(o):
        mi = mathutils.Vector((1e18,) * 3)
        ma = mathutils.Vector((-1e18,) * 3)
        for r in o.bound_box:
            p = o.matrix_world @ mathutils.Vector(r)
            mi = mathutils.Vector(map(min, mi, p))
            ma = mathutils.Vector(map(max, ma, p))
        return mi, ma

    obwiednie = [(o, *obw(o)) for o in czesci]
    x0 = min(mi.x for _, mi, _ in obwiednie)
    y1 = max(ma.y for _, _, ma in obwiednie)         # TYŁ urządzenia
    z_gora = max(ma.z for _, _, ma in obwiednie)     # wierzch panelu

    spis = []
    for i, (o, mi, ma) in enumerate(obwiednie):
        spis.append({
            "nr": i,
            "x_mm": round((mi.x - x0) * skala, 1),
            # y rysunku liczone od TYŁU urządzenia w dół, bo w modelu oś Y
            # rośnie do tyłu, a na rysunku panelu w dół, ku DJ-owi
            "y_mm": round((y1 - ma.y) * skala, 1),
            "szer_mm": round((ma.x - mi.x) * skala, 1),
            "wys_mm": round((ma.y - mi.y) * skala, 1),
            "grubosc_mm": round((ma.z - mi.z) * skala, 1),
            "wystaje_mm": round((ma.z - z_gora) * skala, 1),
            "wierzcholkow": len(o.data.vertices),
        })
    spis.sort(key=lambda s: (s["y_mm"], s["x_mm"]))
    for i, s in enumerate(spis):
        s["nr"] = i

    drobne = [s for s in spis if 3 <= max(s["szer_mm"], s["wys_mm"]) <= 60]
    print(f"części: {len(spis)} · w rozmiarze kontrolki: {len(drobne)}")
    print(f"\n{'nr':>3} {'x':>7} {'y':>7} {'szer':>7} {'wys':>7}  grubość")
    for s in drobne[:40]:
        print(f"{s['nr']:>3} {s['x_mm']:>7.1f} {s['y_mm']:>7.1f} "
              f"{s['szer_mm']:>7.1f} {s['wys_mm']:>7.1f}  {s['grubosc_mm']:>6.1f}")
    if len(drobne) > 40:
        print(f"    …i {len(drobne) - 40} dalszych")

    # podgląd: ponumerowane prostokąty na tle rzutu z góry
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -8 345 470">',
           '<style>text{font:4px sans-serif;fill:#e6e9ee}'
           'rect{fill:none;stroke:#5ee0ff;stroke-width:.5}</style>',
           '<image href="render/cdj_z_gory_orto.png" x="0" y="0" '
           f'width="{SZEROKOSC_MM}" height="453" opacity=".85"/>']
    for s in spis:
        if max(s["szer_mm"], s["wys_mm"]) > 250:
            continue                                  # obudowa
        svg.append(f'<rect x="{s["x_mm"]}" y="{s["y_mm"]}" width="{s["szer_mm"]}" '
                   f'height="{s["wys_mm"]}"/>')
        svg.append(f'<text x="{s["x_mm"] + s["szer_mm"] / 2}" '
                   f'y="{s["y_mm"] + s["wys_mm"] / 2 + 1.5}" '
                   f'text-anchor="middle">{s["nr"]}</text>')
    svg.append("</svg>")
    (TU / "czesci_ponumerowane.svg").write_text("\n".join(svg), encoding="utf-8")

    (TU / "czesci_uklad.json").write_text(json.dumps(
        {"zrodlo": "model 3D, rozdzielenie po wyspach geometrii",
         "uwaga": ("Pozycje z modelu; wymiary bezwzględne rozstrzygnięte na "
                   "korzyść instrukcji (rozjemca_talerz.json). Osie: X szerokość, "
                   "Y głębokość liczona od górnej krawędzi panelu."),
         "skala_mm_na_jednostke": round(skala, 4),
         "panel_mm": {"szerokosc": SZEROKOSC_MM},
         "czesci": spis}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nspis → {TU / 'czesci_uklad.json'}")
    print(f"podgląd → {TU / 'czesci_ponumerowane.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
