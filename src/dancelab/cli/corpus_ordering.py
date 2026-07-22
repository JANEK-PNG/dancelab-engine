"""Read-only commands for the frozen DJ-mix ordering experiment."""

from __future__ import annotations

from pathlib import Path

import typer


app = typer.Typer(
    name="corpus-ordering",
    help="Build and evaluate ordering-given-observed-crate evidence.",
    no_args_is_help=True,
)


def _build_config(
    *,
    min_match_rate: float,
    allow_unreliable_beatgrid: bool,
):
    from dancelab.validation.djmix.ordering import OrderingBuildConfig

    return OrderingBuildConfig(
        min_match_rate=min_match_rate,
        require_reliable_beatgrid=not allow_unreliable_beatgrid,
    )


def _repertoire_config(
    *,
    min_prior_tracks: int,
    min_prior_mixes: int,
    min_selected_tracks: int,
    min_unlabelled_alternatives: int,
    min_identified_fraction: float,
    min_observations: int,
    min_djs: int,
    history_window_days: int | None,
):
    from dancelab.validation.djmix.repertoire import RepertoireBuildConfig

    return RepertoireBuildConfig(
        min_prior_tracks=min_prior_tracks,
        min_prior_mixes=min_prior_mixes,
        min_selected_tracks=min_selected_tracks,
        min_unlabelled_alternatives=min_unlabelled_alternatives,
        min_identified_fraction=min_identified_fraction,
        min_observations=min_observations,
        min_djs=min_djs,
        history_window_days=history_window_days,
    )


@app.command("repertoire-candidates")
def repertoire_candidates(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    output: Path = typer.Option(
        Path("data/reports/revealed_repertoire/candidates.json"),
        "--output",
        "-o",
        help="Untrusted identity/date review queue",
    ),
    review_template_output: Path | None = typer.Option(
        None,
        "--review-template-output",
        help="Optional pending worksheet; it cannot open the gate as generated",
    ),
    expected_ordering_dataset_fingerprint: str | None = typer.Option(
        None,
        "--expect-ordering-dataset",
        help="Pinned ordering dataset fingerprint",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
) -> None:
    """Write candidate hints that cannot enter the model without review."""

    from dancelab.validation.djmix.ordering import (
        OrderingBuildConfig,
        build_corpus_ordering_dataset,
    )
    from dancelab.validation.djmix.repertoire import (
        build_repertoire_candidate_report,
        write_repertoire_candidate_report,
        write_repertoire_review_template,
    )

    try:
        dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=OrderingBuildConfig(min_match_rate=min_match_rate),
        )
        if (
            expected_ordering_dataset_fingerprint is not None
            and dataset.fingerprint != expected_ordering_dataset_fingerprint
        ):
            raise ValueError(
                "ordering dataset fingerprint differs from the pre-registered fingerprint"
            )
        report = build_repertoire_candidate_report(corpus_root, dataset)
        destination = write_repertoire_candidate_report(report, output)
        template_destination = (
            write_repertoire_review_template(report, review_template_output)
            if review_template_output is not None
            else None
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    typer.secho("UNTRUSTED REVIEW QUEUE WRITTEN", fg="yellow")
    typer.echo(f"eligible mixes: {len(report.candidates)}")
    typer.echo(f"solo-like review candidates: {report.counts.get('classification_solo_like', 0)}")
    typer.echo(f"candidate fingerprint: {report.fingerprint}")
    typer.echo("No candidate identity or date has been promoted to ground truth.")
    typer.echo(f"wrote: {destination}")
    if template_destination is not None:
        typer.echo(f"wrote pending review template: {template_destination}")


@app.command("repertoire-gate")
def repertoire_gate(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    review: Path = typer.Option(
        ...,
        "--review",
        help="Human-adjudicated revealed-repertoire review JSON",
    ),
    output: Path = typer.Option(
        Path("data/reports/revealed_repertoire/gate.json"),
        "--output",
        "-o",
        help="Fail-closed revealed-repertoire gate report",
    ),
    candidate_output: Path = typer.Option(
        Path("data/reports/revealed_repertoire/candidates.json"),
        "--candidate-output",
        help="Exact untrusted candidate report used by the gate",
    ),
    dataset_output: Path = typer.Option(
        Path("data/reports/revealed_repertoire/dataset.json"),
        "--dataset-output",
        help="Immutable proxy dataset destination when review is complete",
    ),
    feature_catalog: Path | None = typer.Option(
        None,
        "--features",
        help="Optional complete H/E ordering feature catalogue",
    ),
    analysis_root: Path | None = typer.Option(
        None,
        "--analysis-root",
        help="Optional root containing indexed AnalysisResult JSON files for H",
    ),
    analysis_index: Path | None = typer.Option(
        None,
        "--analysis-index",
        help="Optional proxy track ID to relative AnalysisResult path mapping",
    ),
    embeddings: Path | None = typer.Option(
        None,
        "--embeddings",
        help="Optional frozen learned-audio embedding catalogue for E",
    ),
    expected_ordering_dataset_fingerprint: str | None = typer.Option(
        None,
        "--expect-ordering-dataset",
        help="Pinned ordering dataset fingerprint",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
    min_prior_tracks: int = typer.Option(20, "--min-prior-tracks"),
    min_prior_mixes: int = typer.Option(1, "--min-prior-mixes"),
    min_selected_tracks: int = typer.Option(10, "--min-selected-tracks"),
    min_unlabelled_alternatives: int = typer.Option(
        10,
        "--min-unlabelled-alternatives",
    ),
    min_identified_fraction: float = typer.Option(
        0.8,
        "--min-identified-fraction",
    ),
    min_observations: int = typer.Option(100, "--min-observations"),
    min_djs: int = typer.Option(20, "--min-djs"),
    history_window_days: int | None = typer.Option(
        None,
        "--history-window-days",
    ),
    strict: bool = typer.Option(
        False,
        "--strict/--report-only",
        help="Exit 2 when blocked; report-only still writes gate artifacts",
    ),
) -> None:
    """Build the offline revealed-repertoire proxy and its model gate."""

    from dancelab.validation.djmix.ordering import (
        OrderingBuildConfig,
        build_corpus_ordering_dataset,
    )
    from dancelab.validation.djmix.ordering_models import (
        load_ordering_feature_catalog,
    )
    from dancelab.validation.djmix.repertoire import (
        build_revealed_repertoire_gate,
        write_repertoire_candidate_report,
        write_revealed_repertoire_dataset,
        write_revealed_repertoire_gate,
    )

    try:
        ordering_dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=OrderingBuildConfig(min_match_rate=min_match_rate),
        )
        features = (
            load_ordering_feature_catalog(feature_catalog) if feature_catalog is not None else None
        )
        candidates, report, proxy = build_revealed_repertoire_gate(
            corpus_root,
            ordering_dataset=ordering_dataset,
            review_path=review,
            feature_catalog=features,
            analysis_root=analysis_root,
            analysis_index_path=analysis_index,
            embedding_catalog_path=embeddings,
            config=_repertoire_config(
                min_prior_tracks=min_prior_tracks,
                min_prior_mixes=min_prior_mixes,
                min_selected_tracks=min_selected_tracks,
                min_unlabelled_alternatives=min_unlabelled_alternatives,
                min_identified_fraction=min_identified_fraction,
                min_observations=min_observations,
                min_djs=min_djs,
                history_window_days=history_window_days,
            ),
            expected_ordering_dataset_fingerprint=(expected_ordering_dataset_fingerprint),
        )
        candidates_destination = write_repertoire_candidate_report(
            candidates,
            candidate_output,
        )
        report_destination = write_revealed_repertoire_gate(report, output)
        proxy_destination = (
            write_revealed_repertoire_dataset(proxy, dataset_output) if proxy is not None else None
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    status = "READY" if report.ready_for_proxy_evaluation else "BLOCKED"
    color = "green" if report.ready_for_proxy_evaluation else "yellow"
    typer.secho(f"{status}: revealed-repertoire proxy evaluation", fg=color)
    typer.echo(
        f"review: {report.review.reviewed_count}/{report.review.required_count} "
        f"| approved: {len(report.review.approved_ids)}"
    )
    typer.echo(
        "proxy: "
        f"{report.proxy_dataset.get('observation_count', 0)} observations, "
        f"{report.proxy_dataset.get('dj_count', 0)} DJs"
    )
    if report.source_audio is not None:
        typer.echo(
            "source audio: "
            f"{len(report.source_audio.resolved_sources)}/"
            f"{report.source_audio.required_count}"
        )
    typer.echo(
        f"H: {len(report.handcrafted.available_ids)}/"
        f"{report.handcrafted.required_count}"
    )
    typer.echo(
        f"E: {len(report.embeddings.available_ids)}/"
        f"{report.embeddings.required_count}"
    )
    typer.echo(
        "combined model catalogue: "
        f"{len(report.features.available_ids)}/{report.features.required_count}"
    )
    for blocker in report.blockers:
        typer.secho(f"- {blocker}", fg="yellow")
    typer.echo(f"gate fingerprint: {report.fingerprint}")
    typer.echo(f"wrote: {candidates_destination}")
    typer.echo(f"wrote: {report_destination}")
    if proxy_destination is not None:
        typer.echo(f"wrote: {proxy_destination}")
    else:
        typer.echo("dataset not written: review gate did not open")
    if strict and not report.ready_for_proxy_evaluation:
        raise typer.Exit(code=2)


@app.command("gate")
def gate(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    output: Path = typer.Option(
        Path("data/reports/corpus_ordering/model_gate.json"),
        "--output",
        "-o",
        help="Fail-closed model-gate report destination",
    ),
    queue_output: Path = typer.Option(
        Path("data/reports/corpus_ordering/h_analysis_queue.json"),
        "--queue-output",
        help="Deterministic handcrafted-analysis queue destination",
    ),
    analysis_root: Path | None = typer.Option(
        None,
        "--analysis-root",
        help="Optional root containing indexed AnalysisResult JSON files",
    ),
    analysis_index: Path | None = typer.Option(
        None,
        "--analysis-index",
        help="Optional catalogue-track ID to relative analysis-path mapping",
    ),
    embeddings: Path | None = typer.Option(
        None,
        "--embeddings",
        help="Optional pinned frozen embedding catalogue",
    ),
    dj_mapping: Path | None = typer.Option(
        None,
        "--dj-map",
        help="Optional trusted mix ID to DJ ID mapping",
    ),
    expected_dataset_fingerprint: str | None = typer.Option(
        None,
        "--expect-dataset",
        help="Pinned dataset fingerprint; any mismatch blocks the gate",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
    strict: bool = typer.Option(
        False,
        "--strict/--report-only",
        help="Exit 2 when blocked; report-only still writes the evidence artifacts",
    ),
) -> None:
    """Inspect H/E/DJ readiness and create the exact H work queue.

    This command does not download, transcode, analyze, train, or mutate the
    source corpus. Missing evidence remains visible and blocks strict mode.
    """

    from dancelab.validation.djmix.model_gate import (
        build_ordering_model_gate,
        write_ordering_analysis_queue,
        write_ordering_model_gate,
    )
    from dancelab.validation.djmix.ordering import (
        OrderingBuildConfig,
        build_corpus_ordering_dataset,
    )

    try:
        dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=OrderingBuildConfig(min_match_rate=min_match_rate),
        )
        report, queue = build_ordering_model_gate(
            dataset,
            corpus_root,
            analysis_root=analysis_root,
            analysis_index_path=analysis_index,
            embedding_catalog_path=embeddings,
            dj_mapping_path=dj_mapping,
            expected_dataset_fingerprint=expected_dataset_fingerprint,
        )
        report_destination = write_ordering_model_gate(report, output)
        queue_destination = write_ordering_analysis_queue(queue, queue_output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    status = "READY" if report.ready_for_five_models else "BLOCKED"
    color = "green" if report.ready_for_five_models else "yellow"
    typer.secho(f"{status}: five-model evidence gate", fg=color)
    typer.echo(
        "dataset: "
        f"{report.dataset['observation_count']} observations, "
        f"{report.dataset['mix_count']} mixes, "
        f"{report.dataset['required_track_count']} tracks"
    )
    typer.echo(
        f"H: {len(report.handcrafted.available_ids)}/{report.handcrafted.required_count} "
        f"| queue: {queue.status} ({len(queue.jobs)} job(s))"
    )
    typer.echo(f"E: {len(report.embeddings.available_ids)}/{report.embeddings.required_count}")
    typer.echo(f"DJ: {len(report.dj_identity.available_ids)}/{report.dj_identity.required_count}")
    for blocker in report.blockers:
        typer.secho(f"- {blocker}", fg="yellow")
    typer.echo(f"gate fingerprint: {report.fingerprint}")
    typer.echo(f"wrote: {report_destination}")
    typer.echo(f"wrote: {queue_destination}")
    if strict and not report.ready_for_five_models:
        raise typer.Exit(code=2)


@app.command("prepare-features")
def prepare_features(
    analysis_root: Path = typer.Argument(
        ...,
        help="Root containing indexed DanceLab AnalysisResult JSON files",
    ),
    analysis_index: Path = typer.Option(
        ...,
        "--analysis-index",
        help="Explicit catalogue-track ID to relative analysis-path mapping",
    ),
    embeddings: Path = typer.Option(
        ...,
        "--embeddings",
        help="Precomputed embeddings from one pinned, frozen learned-audio model",
    ),
    dj_mapping: Path = typer.Option(
        ...,
        "--dj-map",
        help="Trusted mix ID to DJ ID mapping with provenance",
    ),
    output: Path = typer.Option(
        Path("data/reports/corpus_ordering/features.json"),
        "--output",
        "-o",
        help="Combined H/E feature catalogue destination",
    ),
) -> None:
    """Build a source-backed H/E catalogue without downloading a model."""

    from dancelab.validation.djmix.ordering_features import (
        build_ordering_feature_catalog,
        write_ordering_feature_catalog,
    )

    try:
        catalog = build_ordering_feature_catalog(
            analysis_root=analysis_root,
            analysis_index_path=analysis_index,
            embedding_catalog_path=embeddings,
            dj_mapping_path=dj_mapping,
        )
        destination = write_ordering_feature_catalog(catalog, output)
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    typer.secho("Source-backed ordering feature catalogue built", fg="green")
    typer.echo(f"tracks: {len(catalog.tracks)}")
    typer.echo(f"H dimensions: {catalog.handcrafted_dimension}")
    typer.echo(f"E dimensions: {catalog.embedding_dimension}")
    typer.echo(f"fingerprint: {catalog.fingerprint}")
    typer.echo(f"wrote: {destination}")


@app.command("build")
def build(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    output: Path = typer.Option(
        Path("data/reports/corpus_ordering/dataset.json"),
        "--output",
        "-o",
        help="Immutable dataset snapshot destination",
    ),
    feature_catalog: Path | None = typer.Option(
        None,
        "--features",
        help="Optional feature catalogue; only its trusted DJ mapping is joined",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
    allow_unreliable_beatgrid: bool = typer.Option(
        False,
        "--allow-unreliable-beatgrid",
        help="Research override; strict reliable-beatgrid gate is the default",
    ),
) -> None:
    """Build Corpus Ordering Dataset v1 without mutating the source corpus."""

    from dancelab.validation.djmix.ordering import (
        build_corpus_ordering_dataset,
        write_ordering_dataset_snapshot,
    )
    from dancelab.validation.djmix.ordering_models import (
        load_ordering_feature_catalog,
    )

    try:
        catalog = (
            load_ordering_feature_catalog(feature_catalog) if feature_catalog is not None else None
        )
        dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=_build_config(
                min_match_rate=min_match_rate,
                allow_unreliable_beatgrid=allow_unreliable_beatgrid,
            ),
            dj_by_mix=catalog.dj_by_mix if catalog is not None else None,
        )
        destination = write_ordering_dataset_snapshot(dataset, output)
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    typer.secho("Corpus Ordering Dataset v1 built", fg="green")
    typer.echo(f"observations: {len(dataset.observations)}")
    typer.echo(f"mixes: {len(dataset.mix_ids)}")
    typer.echo(f"fingerprint: {dataset.fingerprint}")
    typer.echo(f"wrote: {destination}")


@app.command("check")
def check(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    feature_catalog: Path = typer.Option(
        ...,
        "--features",
        help="Source-backed H/E vectors and trusted DJ IDs",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
) -> None:
    """Report whether the corpus can support the declared five-model test."""

    from dancelab.validation.djmix.ordering import (
        OrderingBuildConfig,
        build_corpus_ordering_dataset,
    )
    from dancelab.validation.djmix.ordering_models import (
        assess_ordering_model_readiness,
        load_ordering_feature_catalog,
    )

    try:
        catalog = load_ordering_feature_catalog(feature_catalog)
        dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=OrderingBuildConfig(min_match_rate=min_match_rate),
            dj_by_mix=catalog.dj_by_mix,
        )
        readiness = assess_ordering_model_readiness(dataset, catalog)
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    color = "green" if readiness.ready_for_five_models else "yellow"
    status = "READY" if readiness.ready_for_five_models else "BLOCKED"
    typer.secho(f"{status}: five-model ordering evaluation", fg=color)
    typer.echo(f"observations: {readiness.eligible_observations}/{readiness.total_observations}")
    typer.echo(f"eligible mixes: {readiness.eligible_mix_count}")
    typer.echo(f"trusted DJs: {readiness.eligible_dj_count}")
    for blocker in readiness.blockers:
        typer.secho(f"- {blocker}", fg="yellow")
    if not readiness.ready_for_five_models:
        raise typer.Exit(code=2)


@app.command("evaluate")
def evaluate(
    corpus_root: Path = typer.Argument(..., help="Frozen DanceLabCorpus root"),
    feature_catalog: Path = typer.Option(
        ...,
        "--features",
        help="Source-backed H/E vectors and trusted DJ IDs",
    ),
    output: Path = typer.Option(
        Path("data/reports/corpus_ordering/five_model_report.json"),
        "--output",
        "-o",
    ),
    min_match_rate: float = typer.Option(0.4, "--min-match-rate"),
    l2: float = typer.Option(0.1, "--l2"),
    dj_l2: float = typer.Option(1.0, "--dj-l2"),
    max_iterations: int = typer.Option(400, "--max-iterations"),
    include_model_parameters: bool = typer.Option(
        False,
        "--include-model-parameters",
    ),
) -> None:
    """Run L0/LH/LE/LHE/LHEI on one immutable held-out universe."""

    from dancelab.validation.djmix.ordering import (
        OrderingBuildConfig,
        build_corpus_ordering_dataset,
    )
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig,
        load_ordering_feature_catalog,
        train_five_model_ordering_evaluation,
        write_five_model_ordering_report,
    )

    try:
        catalog = load_ordering_feature_catalog(feature_catalog)
        dataset = build_corpus_ordering_dataset(
            corpus_root,
            config=OrderingBuildConfig(min_match_rate=min_match_rate),
            dj_by_mix=catalog.dj_by_mix,
        )
        report = train_five_model_ordering_evaluation(
            dataset,
            catalog,
            config=OrderingTrainingConfig(
                l2=l2,
                dj_l2=dj_l2,
                max_iterations=max_iterations,
            ),
        )
        destination = write_five_model_ordering_report(
            report,
            output,
            include_model_parameters=include_model_parameters,
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(f"BLOCKED: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from exc

    typer.secho("Five-model held-out evaluation complete", fg="green")
    for name, metrics in report.test_metrics.items():
        typer.echo(f"{name}: total NLL {metrics.total_nll:.4f} | top-1 {metrics.top1_accuracy:.1%}")
    typer.echo(
        "decomposition: "
        f"C_rule={report.decomposition.c_rule:.3f}, "
        f"C_sim={report.decomposition.c_similarity:.3f}, "
        f"I={report.decomposition.identity:.3f}, "
        f"N={report.decomposition.residual:.3f}"
    )
    for warning in report.warnings:
        typer.secho(f"warn: {warning}", fg="yellow")
    typer.echo(f"evaluation hash: {report.evaluation_hash}")
    typer.echo(f"wrote: {destination}")
