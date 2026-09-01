"""Accounting for scoring components that fail quietly during measurement.

A measurement script that wraps a component in `except Exception: pass` still
produces numbers when the component never runs. Those numbers look ordinary and
answer a different question than the one in the heading.

That is not hypothetical here. `priors_validation.py` multiplied a
`HarmonicResult` by a float, the `TypeError` went into a bare except, and for
three weeks "measured weights beat hand-set weights" was really "a model with
harmony beats the same model without it" (D6 in OBALONE.md). The fix for the
multiplication took minutes; the reason it survived three weeks was that
nothing counted the skips.

Usage in a script:

    from dancelab.validation.skladniki import Skladniki

    skl = Skladniki()
    ...
    skl.probuje("hand.harmonic")
    try:
        s += 0.4 * harmonic_compatibility(a, b).harmonic_compatibility_score
    except Exception as exc:
        skl.pominiete("hand.harmonic", exc)
    ...
    print(skl.raport())          # human-readable, names what dropped out
    json.dumps(skl.jako_dict())  # travels with the result artifact
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Wpis:
    prob: int = 0
    pominiete: int = 0
    przyczyna: str | None = None


@dataclass
class Skladniki:
    """Counts attempts and silent skips per named scoring component."""

    wpisy: dict[str, _Wpis] = field(default_factory=dict)

    def probuje(self, nazwa: str) -> None:
        self.wpisy.setdefault(nazwa, _Wpis()).prob += 1

    def pominiete(self, nazwa: str, exc: BaseException) -> None:
        """Record a skip. The first cause is kept — count without cause is a dead end."""
        wpis = self.wpisy.setdefault(nazwa, _Wpis())
        wpis.pominiete += 1
        if wpis.przyczyna is None:
            wpis.przyczyna = repr(exc)

    def nieobecne(self) -> list[str]:
        """Components that failed on EVERY attempt — the D6 case exactly."""
        return sorted(n for n, w in self.wpisy.items()
                      if w.prob and w.pominiete == w.prob)

    def jako_dict(self) -> dict[str, dict]:
        return {n: {"prob": w.prob, "pominiete": w.pominiete,
                    "przyczyna": w.przyczyna}
                for n, w in sorted(self.wpisy.items())}

    def raport(self) -> str:
        if not self.wpisy:
            return "składniki: nic nie było liczone — sprawdź dane wejściowe"
        linie = []
        for nazwa, w in sorted(self.wpisy.items()):
            if w.pominiete == 0:
                linie.append(f"  {nazwa:<20} {w.prob:>7} prób, wszystkie policzone")
                continue
            udzial = w.pominiete / w.prob * 100 if w.prob else 0.0
            etykieta = ("NIEOBECNY W WYNIKU" if w.pominiete == w.prob
                        else "częściowo pominięty")
            linie.append(f"  {nazwa:<20} {w.prob:>7} prób, POMINIĘTE "
                         f"{w.pominiete} ({udzial:.1f}%) → {etykieta}")
            linie.append(f"  {'':<20} przyczyna: {w.przyczyna}")
        if self.nieobecne():
            linie += [
                "",
                "  UWAGA: " + ", ".join(self.nieobecne()) + " nie wszedł do ŻADNEJ pary.",
                "  Wynik powyżej nie mierzy tego, co obiecuje jego nagłówek —",
                "  tak powstał obalony wynik D6. Napraw składnik przed cytowaniem liczb.",
            ]
        return "\n".join(linie)
