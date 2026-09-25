"""Create a reproducible synthetic ToF-ERD spectrum and automatic polygons."""

import argparse
import csv
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import build_candidate_histogram
from modules.tofe_candidate import propose_banana_candidates
from modules.tofe_candidate_metrics import evaluate_candidate_truth
from modules.tofe_candidate_metrics import summarize_candidate_metrics
from modules.tofe_synthetic import TofeGeometry
from modules.tofe_synthetic import generate_synthetic_events
from modules.tofe_training_data import AcceptedSelection
from modules.tofe_training_data import build_training_feature_rows
from modules.tofe_training_data import training_rows_tsv


def run_demo(output_directory):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    geometry = TofeGeometry()
    dataset = generate_synthetic_events(
        geometry=geometry,
        channel_shifts={
            "1H": (2.0, -5.0),
            "12C": (-1.5, 7.0),
            "16O": (1.0, 5.0),
            "28Si": (-2.0, -6.0),
        },
    )
    grid = build_candidate_histogram(
        dataset.tof_channel,
        dataset.energy_channel,
        tof_compression=2.0,
        energy_compression=8.0,
        max_bin_count=1200,
    )
    candidates = propose_banana_candidates(
        grid.counts,
        grid.tof_edges,
        grid.energy_edges,
        dataset.loci,
        CandidateSearchSettings(
            sample_count=60,
            search_radius_fwhm=2.0,
            polygon_half_width_fwhm=1.6,
            minimum_peak_sigma=2.0,
            minimum_coverage=0.35,
            minimum_confidence=0.18,
        ),
    )
    metrics = evaluate_candidate_truth(
        candidates,
        dataset.tof_channel,
        dataset.energy_channel,
        dataset.truth_label,
        expected_labels=[locus.label for locus in dataset.loci],
    )
    metric_by_label = {metric.label: metric for metric in metrics}
    summary = summarize_candidate_metrics(metrics)
    training_rows = build_training_feature_rows(
        dataset.tof_channel,
        dataset.energy_channel,
        tuple(AcceptedSelection(
            selection_id=candidate.label,
            label=candidate.label,
            polygon=candidate.polygon,
        ) for candidate in candidates),
        loci=dataset.loci,
        measurement_id="synthetic-kist-preset",
    )

    np.savez_compressed(
        output_directory / "synthetic_tofe_events.npz",
        tof_channel=dataset.tof_channel,
        energy_channel=dataset.energy_channel,
        truth_label=dataset.truth_label,
    )
    with (output_directory / "autoselection_summary.tsv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow((
            "element", "confidence", "coverage", "contrast",
            "theory_adherence", "event_precision", "event_recall",
            "event_f1", "event_iou", "true_positive", "false_positive",
            "false_negative", "polygon_vertices",
        ))
        for candidate in candidates:
            metric = metric_by_label[candidate.label]
            writer.writerow((
                candidate.label,
                f"{candidate.confidence:.4f}",
                f"{candidate.coverage:.4f}",
                f"{candidate.contrast:.4f}",
                f"{candidate.theory_adherence:.4f}",
                f"{metric.precision:.4f}",
                f"{metric.recall:.4f}",
                f"{metric.f1:.4f}",
                f"{metric.event_iou:.4f}",
                metric.true_positive,
                metric.false_positive,
                metric.false_negative,
                candidate.polygon.shape[0],
            ))
    (output_directory / "ml_training_rows.tsv").write_text(
        training_rows_tsv(training_rows), encoding="utf-8"
    )

    figure, axis = plt.subplots(figsize=(12, 7.2), constrained_layout=True)
    image = axis.pcolormesh(
        grid.tof_edges,
        grid.energy_edges,
        np.log1p(grid.counts),
        shading="auto",
        cmap="magma",
    )
    for locus in dataset.loci:
        axis.plot(
            locus.tof_channel,
            locus.energy_channel,
            color="#6ECFF6",
            linewidth=1.0,
            linestyle="--",
            alpha=0.9,
        )
        axis.text(
            locus.tof_channel[-1],
            locus.energy_channel[-1],
            f" {locus.label}",
            color="white",
            fontsize=10,
            fontweight="bold",
        )
    for candidate in candidates:
        axis.plot(
            candidate.polygon[:, 0],
            candidate.polygon[:, 1],
            color="#35E3A1",
            linewidth=1.8,
        )
        axis.plot(
            candidate.ridge[:, 0],
            candidate.ridge[:, 1],
            color="#F8F9FA",
            linewidth=0.9,
        )
        axis.text(
            candidate.ridge[-1, 0],
            candidate.ridge[-1, 1],
            f" {candidate.label} conf {candidate.confidence:.0%} "
            f"IoU {metric_by_label[candidate.label].event_iou:.0%}",
            color="#35E3A1",
            fontsize=9,
        )
    axis.set_title(
        "Synthetic ToF-ERD automatic banana selection\n"
        f"{geometry.beam_label}, {geometry.beam_energy_mev:.1f} MeV, "
        f"recoil {geometry.recoil_angle_deg:.0f}°, "
        f"incidence/exit {geometry.incidence_angle_deg:.0f}°/"
        f"{geometry.exit_angle_deg:.0f}°"
    )
    axis.set_xlabel("ToF channel")
    axis.set_ylabel("Energy channel")
    colorbar = figure.colorbar(image, ax=axis)
    colorbar.set_label("log(1 + counts)")
    figure.savefig(output_directory / "synthetic_autoselection.png", dpi=180)
    plt.close(figure)

    return dataset, candidates, metrics, summary, training_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/tofe_synthetic_demo")
    arguments = parser.parse_args()
    dataset, candidates, metrics, summary, training_rows = run_demo(
        arguments.output
    )
    print(f"beam_energy_mev={dataset.geometry.beam_energy_mev:.3f}")
    print(f"events={dataset.tof_channel.size}")
    print(f"candidates={len(candidates)}")
    metric_by_label = {metric.label: metric for metric in metrics}
    for candidate in candidates:
        metric = metric_by_label[candidate.label]
        print(
            f"{candidate.label}: confidence={candidate.confidence:.3f}, "
            f"coverage={candidate.coverage:.3f}, "
            f"precision={metric.precision:.3f}, "
            f"recall={metric.recall:.3f}, IoU={metric.event_iou:.3f}"
        )
    print(
        f"micro_precision={summary.precision:.3f}, "
        f"micro_recall={summary.recall:.3f}, "
        f"micro_f1={summary.f1:.3f}, "
        f"micro_iou={summary.event_iou:.3f}"
    )
    print(
        f"training_rows={len(training_rows)}, "
        f"training_features={len(training_rows[0].as_dict()) if training_rows else 0}"
    )


if __name__ == "__main__":
    main()
