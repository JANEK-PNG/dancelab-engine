"""Identity catalog: one register tying DanceLab's separate ID systems together.

The engine grew five independent identifier spaces that never met:

* the DJ map spreadsheet (``A00001`` / ``U000001`` / ``S000001``),
* our own analyses (``rb{ContentID}`` or a content hash),
* corpus mixes (``mix0022``) and their YouTube video IDs,
* Rekordbox ``ContentID``,
* CLAP embedding keys (file path for the local library, video ID for corpus).

This package holds identity and relations in PostgreSQL; the heavy payload
(audio, analysis frames, MIDI registries) stays on disk and is referenced by
path plus checksum. Every cross-system link records the method that produced
it and a confidence, because a name match is not identity.
"""

from dancelab.catalog.db import connect, database_url

__all__ = ["connect", "database_url"]
