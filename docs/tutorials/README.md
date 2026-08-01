# DanceLab Terminal Tutorials

These tutorials are the supported user path for the headless DanceLab engine.
Every lesson is both onboarding and a bounded regression check: it names the
input, the command, the expected artifact, and the failure signals.

## Learning Path

1. [Build a first set](01_beginner_first_flow.md)
2. [Shape and inspect a real set](02_intermediate_corpus_set_workflows.md)
3. [Run a disciplined validation round](03_advanced_validation_review.md)

The progression is:

`inspect -> analyze -> generate -> listen -> validate -> export`

## Product Boundary

- The engine computes analysis, ranking, timing, and export data.
- The CLI is the supported control surface.
- The optional HTTP API is a localhost integration surface.
- CSV, JSON, Markdown, XML, and WAV files carry results out of the engine.
- There is no supported desktop or browser application.

Start by checking the installed command:

```bash
dancelab --help
```

Related documentation:

- [Project README](../../README.md)
- [Validation](../validation.md)
- [Architecture](../architecture.md)
