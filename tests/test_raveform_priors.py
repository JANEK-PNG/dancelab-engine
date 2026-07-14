from __future__ import annotations

import json
import zipfile

import numpy as np

from dancelab.validation.raveform.dataset import (
    load_raveform_observations,
    quantize_duration_beats,
)
from dancelab.validation.raveform.models import TransitionObservation
from dancelab.validation.raveform.training import (
    PRIOR_STRENGTH_CANDIDATES,
    split_by_mix,
    train_raveform_prior,
)


def _observation(
    mix_index: int,
    duration: int,
    *,
    genre: str,
    outgoing: str | None = None,
    incoming: str | None = None,
) -> TransitionObservation:
    return TransitionObservation(
        mix_id=f"mix{mix_index:04d}",
        previous_track_id=f"previous-{mix_index}",
        next_track_id=f"next-{mix_index}",
        overlap_beats=float(duration),
        duration_bucket_beats=duration,
        genres=(genre,),
        outgoing_section=outgoing,
        incoming_section=incoming,
        previous_match_rate=0.9,
        next_match_rate=0.85,
    )


def test_duration_quantization_uses_supported_buckets_and_lower_ties():
    assert quantize_duration_beats(1.0) == 32
    assert quantize_duration_beats(47.9) == 32
    assert quantize_duration_beats(48.0) == 32
    assert quantize_duration_beats(48.1) == 64
    assert quantize_duration_beats(255.0) == 256


def test_grouped_split_has_no_mix_leakage():
    observations = tuple(
        _observation(index // 2, 64 if index % 2 else 96, genre="house")
        for index in range(30)
    )

    splits = split_by_mix(observations, seed="fixture")
    mix_sets = {
        name: {item.mix_id for item in values}
        for name, values in splits.items()
    }

    assert mix_sets["train"].isdisjoint(mix_sets["validation"])
    assert mix_sets["train"].isdisjoint(mix_sets["test"])
    assert mix_sets["validation"].isdisjoint(mix_sets["test"])
    assert sum(len(values) for values in splits.values()) == len(observations)


def test_training_emits_smoothed_context_priors_and_held_out_metrics():
    observations = []
    for index in range(60):
        if index % 2:
            observations.append(_observation(
                index,
                64 if index % 5 else 96,
                genre="house",
                outgoing="outro",
                incoming="intro",
            ))
        else:
            observations.append(_observation(
                index,
                128 if index % 6 else 160,
                genre="techno",
                outgoing="drop",
                incoming="buildup",
            ))

    model, report = train_raveform_prior(observations, split_seed="fixture-model")

    assert np.isclose(sum(model.global_distribution.probabilities), 1.0)
    assert np.isclose(sum(model.genre_distributions["house"].probabilities), 1.0)
    assert model.genre_prior_strength in PRIOR_STRENGTH_CANDIDATES
    assert model.section_prior_strength in PRIOR_STRENGTH_CANDIDATES
    assert not model.calibrated_probability
    assert report["eligible_for_engine_influence"] is False
    assert report["split"]["mix_id_overlap"] == 0
    assert set(report["selection"]["context_gates"]) == {"genre", "section_pair"}
    assert isinstance(report["selection"]["context_gates"]["genre"]["enabled"], bool)
    assert isinstance(
        report["selection"]["context_gates"]["section_pair"]["enabled"],
        bool,
    )
    assert report["held_out_metrics"]["global_test"]["count"] > 0


def test_unknown_context_falls_back_to_global_distribution():
    observations = tuple(
        _observation(
            index,
            64,
            genre="house",
            outgoing="outro",
            incoming="intro",
        )
        for index in range(20)
    )
    model, _ = train_raveform_prior(observations, split_seed="fixture-fallback")

    probabilities, source = model.predict(
        genres=("unknown-style",),
        outgoing_section="bridge",
        incoming_section="drop",
    )

    assert source == "global"
    assert probabilities == model.global_distribution.probabilities


def test_archive_loader_reconstructs_strict_adjacent_transition(tmp_path):
    archive_path = tmp_path / "raveform.zip"
    mix = {
        "id": "mix0001",
        "genres": ["UK Garage"],
        "tracklist": [
            {"id": "track-a", "title": "A"},
            {"id": "track-b", "title": "B"},
        ],
    }
    structures = [
        {
            "id": "track-a",
            "sections": [{"name": "outro", "start": 0.0, "end": 120.0}],
        },
        {
            "id": "track-b",
            "sections": [{"name": "intro", "start": 0.0, "end": 30.0}],
        },
    ]
    alignments = [
        {
            "mix_id": "mix0001",
            "track_id": "track-a",
            "mixin_beat_mix": 0,
            "mixout_beat_mix": 100,
            "mixin_time_track": 0.0,
            "mixout_time_track": 90.0,
            "match_rate": 0.9,
        },
        {
            "mix_id": "mix0001",
            "track_id": "track-b",
            "mixin_beat_mix": 40,
            "mixout_beat_mix": 160,
            "mixin_time_track": 5.0,
            "mixout_time_track": 110.0,
            "match_rate": 0.8,
        },
    ]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("raveform/mixes.jsonl", json.dumps(mix) + "\n")
        archive.writestr("raveform/structures/segments.json", json.dumps(structures))
        archive.writestr("raveform/beats/tracks/track-a.beat.json", "{}")
        archive.writestr("raveform/beats/tracks/track-b.beat.json", "{}")
        archive.writestr(
            "raveform/alignments/mix0001.align.jsonl",
            "\n".join(json.dumps(item) for item in alignments) + "\n",
        )

    observations, audit = load_raveform_observations(archive_path)

    assert len(observations) == 1
    observation = observations[0]
    assert observation.overlap_beats == 60.0
    assert observation.duration_bucket_beats == 64
    assert observation.genres == ("uk garage",)
    assert observation.section_pair == "outro>intro"
    assert audit["inventory"]["qualified_adjacent_pairs"] == 1
    assert audit["inventory"]["positive_overlap_observations"] == 1
    assert audit["quality"]["duplicate_primary_rows"] == 0
    assert audit["quality"]["same_track_on_both_sides"] == 0
    assert audit["quality"]["genre_context_coverage"] == 1.0
    assert audit["quality"]["section_pair_coverage"] == 1.0
