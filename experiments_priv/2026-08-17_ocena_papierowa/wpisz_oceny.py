"""Przepisanie ocen z papieru (skan CamScanner 29.08) do arkuszy.

Źródło: `skany/oceny_2026-08-29.pdf`, 16 stron, formularz `formularz_oceny.html`.
Każda ocena przeczytana ze zdjęcia kartki. **Nic nie jest zgadywane**: pola,
których nie dało się odczytać jednoznacznie, zostają PUSTE i idą do Janka jako
pytanie. Bramka kompletności w `analiza.py` i tak nie ruszy, dopóki wszystkie
158 przejść nie ma oceny.

Poprawki na papierze (cyfra przekreślona, druga zakreślona) czytane jako
OSTATNIA wola: liczy się zakreślona, nie przekreślona.
"""

import csv
import pathlib

TU = pathlib.Path(__file__).parent

# (ocena, kategorie zgrzytu, notatka) — None w ocenie = nieczytelne, zostaw puste
OCENY: dict[str, list] = {
    "OCENA_A": [
        (5, "", "wzorowo"),
        (5, "", "wzorowo"),
        (5, "", "wzorowo"),
        (5, "", "wzorowo"),
        (1, "", "DL hits — to sample"),
        (1, "", "Nu 8beat to loop"),
        (5, "", "poprawka: 4 przekreślone, 5 zakreślone; dwie zmiany energii między 4 a 7"),
        (5, "", "wzorowo"),
        (5, "", "wzorowo"),
        (5, "", "wzorowo"),
        (5, "D", "drugi raz z tej samej składanki — ale siedzi i się broni, uzasadnione"),
        (4, "T", "zły grid, przesunięcie na Kim Kaey"),
        (4, "T", "przesunięcie na Kim Kaey"),
        (3, "T,E", "trochę energia zastyga, lekki offgrid na Celebrations"),
        (2, "S,E,K", "Tales from... wybija narzucony klimat, mocno spowalnia energię"),
        (3, "S,E,K", "przeszliśmy z pogodnego na mroczny i z powrotem"),
        (5, "", "złoto!!!"),
        (5, "", "wzorowo"),
        (1, "S,E", "psuje zakończenie, ostatni utwór"),
    ],
    "OCENA_B": [
        (5, "", "świat A"),
        (4, "D,K", "poprawka: 3 przekreślone, 4 zakreślone; świat A"),
        (2, "S,K", "świat A -> B, nieładny"),
        (4, "K", "świat B"),
        (4, "T", "B, coś z gridem, coś się wleczyło"),
        (2, "", "introspekt na nieregularne bity, za dużo zderzeń"),
        (2, "S,E,K", ""),
        (4, "", "poprawka: 3 przekreślone, 4 zakreślone; świat B -> świat C"),
        (5, "", "perła w stosie gówna (C)"),
        (5, "", "na koniec mamy przejście top!"),
        (5, "", ""),
    ],
    "OCENA_C": [(5, "", "") for _ in range(24)],
    "OCENA_D": [
        (3, "S,E", ""),
        (3, "S,E", ""),
        (3, "S,E", ""),
        (3, "S,E", ""),
        (3, "", ""),
        (4, "", ""),
        (5, "", ""),
    ],
    "OCENA_E": [
        (1, "T", "miksowanie z samplem"),
        (1, "T", "miksowanie z samplem"),
        (5, "", ""),
        (5, "", "wybitne!"),
        (5, "", "wybitne!"),
        (5, "", "poprawka: 4 przekreślone, 5 zakreślone"),
        (5, "", "wybitne!"),
        (5, "", "wybitne!"),
        (5, "", "klasa!"),
        (5, "", ""),
        (5, "", "pojebanie do siebie pasują"),
        (5, "", ""),
        (5, "", "poprawka: 3 przekreślone, 5 zakreślone; kategorie T i K przekreślone. "
                "Muzyka jako tako pasuje, ale jest coś nie tak z gridem"),
        (3, "T,K", "do 14 feedback"),
        (4, "T", "grid się rozjeżdża, ale zestawienie top"),
        (5, "", "fire!!!"),
        (5, "", "top!!"),
    ],
    "OCENA_F": [
        (2, "K", ""),
        (5, "", ""),
        (1, "T,E,K", "YAANO ma 170 BPM"),
        (1, "K", "-11-11-11-"),
        (1, "E,K", "inne światy"),
        (1, "E,K", ""),
        (2, "E", "teoretycznie można skleić"),
        (2, "E", ""),
        (5, "", "podróż!"),
        (5, "", ""),
        (5, "", ""),
        (3, "", ""),
        (5, "", ""),
        (5, "", "na koniec rozpierdol, miła odmiana"),
    ],
    "OCENA_G": [
        (3, "E", ""),
        (3, "K", ""),
        (4, "", "poprawka: 4 zakreślone, 5 przekreślone"),
        (5, "", ""),
        (4, "E", "poprawka: 4 zakreślone, 5 przekreślone"),
        (5, "", ""),
        (4, "E", ""),
        (3, "E", "znaczący spadek energii"),
        (4, "T,K", "zmiana stylu"),
        (5, "", ""),
        (4, "E", ""),
        (3, "E", "poprawka: 3 zakreślone, 4 przekreślone"),
        (4, "", ""),
        (4, "", ""),
        (5, "", ""),
        (5, "", "fire!"),
        (5, "", ""),
        (4, "E", "PAURRO fajny, ale bardziej do setu Four Tet"),
        (4, "", "poprawka: 3 przekreślone, 4 zakreślone"),
        (3, "K", ""),
        (3, "", ""),
    ],
    "OCENA_H": [
        (5, "", ""),
        (2, "E,K", ""),
        (4, "K", ""),
        (4, "", ""),
        (2, "T,K", ""),
        (3, "K", ""),
        (3, "E,K", "zmiana stylów"),
        (3, "", ""),
        (3, "", ""),
    ],
    "OCENA_I": [
        (3, "E", ""),
        (2, "M", ""),
        (4, "", ""),
        (4, "", ""),
        (4, "", ""),
        (4, "E", "zakreślone 4, obok dopisane „5?”; Janek rozstrzygnął 29.08: 4. "
                 "Dobry pomysł na outro"),
        (4, "", ""),
        (1, "T,S,E,M,D,K", "„rock?”, „nie wiem” — wszystkie kategorie zakreślone"),
        (1, "T,S,E,M,D,K", ""),
        (5, "K", ""),
        (4, "K", ""),
        (4, "K", "dobre na intro"),
        (2, "E,K", ""),
        (3, "", ""),
        (3, "K", ""),
        (1, "", "zakreślone jednocześnie 1 i 2; Janek rozstrzygnął 29.08: 1. „Inny świat”"),
        (3, "T", ""),
        (3, "", ""),
        (5, "", "fire!"),
        (2, "E", ""),
        (1, "E", ""),
        (5, "", "poprawka: 3 przekreślone, 5 zakreślone"),
        (4, "E", ""),
    ],
    "OCENA_J": [
        (4, "", ""),
        (4, "", "zakreślone jednocześnie 4 i 5; Janek rozstrzygnął 29.08: 4"),
        (3, "E", ""),
        (5, "", ""),
        (4, "", "zakreślone jednocześnie 4 i 5; Janek rozstrzygnął 29.08: 4"),
        (3, "", ""),
        (3, "", ""),
        (2, "", ""),
        (2, "", ""),
        (3, "", ""),
        (3, "", ""),
        (3, "", ""),
        (3, "", "na papierze nie było zakreślonej cyfry; Janek odsłuchał to przejście "
                "29.08 i ocenił na 3 — ZANIM zobaczył jakikolwiek wynik analizy "
                "i nie wiedząc, czy OCENA J to silnik, czy kontrola"),
    ],
}

# playlista: (spójność, różnorodność, przebieg, zagrałbym, uwaga)
PLAYLISTY = {
    "OCENA A": (4, 4, 3, 4,
                "Ogólnie stylistycznie set się trzyma do 13 przejścia. "
                "Później mocno odpada i na koniec wraca na wyznaczony tor"),
    "OCENA B": (1, 4, 1, 2, "Trzy światy, trzy różne sety. Najmocniej od 8 do 11"),
    "OCENA C": (5, 5, 5, 5, "Ten set to dzieło sztuki. Czy to nie jest kopia czyjegoś setu?"),
    "OCENA D": (3, 3, 3, 2, "Przejście między 7 a 8 ma coś do zaoferowania jedynie"),
    "OCENA E": (5, 5, 5, 5,
                "Kolejna pojebana playlista. Muszę mieć pewność, że to wyszło "
                "z silnika i nie jest kopią czyjegoś setu"),
    "OCENA F": (1, 3, 2, 2,
                "Tak naprawdę od 9 do 14 możemy mówić o spójnym secie. "
                "Ostatnia nuta kozacka"),
    "OCENA G": (3, 3, 3, 3,
                "Set nie wie, w jakim stylu podążać. Energia się zmienia i nastrój "
                "tak samo, raz jest mrocznie, a raz wesoło. 20 i 21 brzmią nagle, "
                "jakby ktoś grał na Tomorrowland main stage — nijak się ma do całości"),
    "OCENA H": (2, 3, 2, 2,
                "Zmiana energii i klimatu. Za duży miszmasz. "
                "Nie broni się nawet jako set eksperymentalny"),
    "OCENA I": (1, 1, 1, 1, "Koszmarna playlista. Nigdy nie róbmy czegoś tak gównianego"),
    "OCENA J": (3, 3, 3, 3, ""),
}


def main() -> int:
    wpisane = puste = 0
    for plik in sorted(TU.glob("SESJA_*_transition_ratings.csv")):
        wiersze = list(csv.DictReader(plik.open(encoding="utf-8")))
        pola = list(wiersze[0].keys())
        # Kategorie zgrzytu MUSZĄ mieć własną kolumnę. Wrzucone razem z notatką
        # do `comment` psuły liczenie: licznik szukał liter T/S/E/M/D/K w całym
        # tekście, a polskie zdanie zawiera je wszystkie („Nu 8beat to loop"
        # dawało E i T). Złapane 29.08 po pierwszym przebiegu analizy.
        if "zgrzyt" not in pola:
            pola.insert(pola.index("comment"), "zgrzyt")
        for w in wiersze:
            plej, nr = w["pair_id"].rsplit("_", 1)
            ocena, kat, notka = OCENY[plej][int(nr) - 1]
            if ocena is None:
                puste += 1
            else:
                w["dj_mixability_rating"] = str(ocena)
                wpisane += 1
            w["zgrzyt"] = kat
            w["comment"] = notka
        with plik.open("w", newline="", encoding="utf-8") as f:
            pis = csv.DictWriter(f, fieldnames=pola)
            pis.writeheader()
            pis.writerows(wiersze)
        print(f"{plik.name}: {len(wiersze)} wierszy")

    p = TU / "oceny_playlist.csv"
    wiersze = list(csv.DictReader(p.open(encoding="utf-8")))
    pola = list(wiersze[0].keys())
    for w in wiersze:
        s, r, pb, z, uw = PLAYLISTY[w["playlista"]]
        w.update({"spojnosc": s, "roznorodnosc": r, "przebieg": pb,
                  "zagralbym": z, "uwaga": uw})
    with p.open("w", newline="", encoding="utf-8") as f:
        pis = csv.DictWriter(f, fieldnames=pola)
        pis.writeheader()
        pis.writerows(wiersze)

    print(f"\nwpisane: {wpisane} · do potwierdzenia (puste): {puste} · razem 158")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
