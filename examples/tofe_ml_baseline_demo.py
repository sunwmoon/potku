"""Train the optional confidence baseline on reproducible synthetic decisions."""

import argparse
import csv
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import numpy as np

from examples.tofe_autoselection_demo import run_demo
from modules.tofe_ml import fit_baseline_correction_model
from modules.tofe_ml import save_baseline_correction_model
from modules.tofe_training_data import AcceptedSelection
from modules.tofe_training_data import build_training_feature_rows
from modules.tofe_training_data import training_rows_tsv


def run_ml_demo(output_directory):
    output_directory = Path(output_directory)
    dataset, candidates, metrics, summary, _ = run_demo(output_directory)
    loci = {locus.label: locus for locus in dataset.loci}
    selections = []
    for candidate in candidates:
        selections.append(AcceptedSelection(
            selection_id=f"{candidate.label}:accepted",
            label=candidate.label,
            polygon=candidate.polygon,
            target_accepted=1,
        ))
        locus = loci[candidate.label]
        poor_offset = np.array([
            10 * locus.tof_resolution_fwhm_channel,
            10 * locus.energy_resolution_fwhm_channel,
        ])
        selections.append(AcceptedSelection(
            selection_id=f"{candidate.label}:rejected-shift",
            label=candidate.label,
            polygon=candidate.polygon + poor_offset,
            target_accepted=0,
        ))

    rows = build_training_feature_rows(
        dataset.tof_channel,
        dataset.energy_channel,
        selections,
        dataset.loci,
        measurement_id="synthetic-review-decisions",
    )
    model = fit_baseline_correction_model(rows)
    probabilities = model.predict_probability(rows)
    predicted = probabilities >= 0.5
    targets = np.asarray([row.target_accepted for row in rows], dtype=bool)
    accuracy = float(np.mean(predicted == targets))

    (output_directory / "ml_review_training_rows.tsv").write_text(
        training_rows_tsv(rows), encoding="utf-8"
    )
    save_baseline_correction_model(
        model, output_directory / "baseline_confidence_model.json"
    )
    with (output_directory / "ml_baseline_predictions.tsv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow((
            "selection_id", "label", "target_accepted",
            "ml_probability", "predicted_accepted",
        ))
        for row, probability, decision in zip(
                rows, probabilities, predicted):
            writer.writerow((
                row.selection_id,
                row.label,
                row.target_accepted,
                f"{probability:.6f}",
                int(decision),
            ))
    return {
        "events": int(dataset.tof_channel.size),
        "candidates": len(candidates),
        "micro_f1": summary.f1,
        "event_iou": summary.event_iou,
        "training_rows": len(rows),
        "positive_mean": float(np.mean(probabilities[targets])),
        "negative_mean": float(np.mean(probabilities[~targets])),
        "training_accuracy": accuracy,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/tofe_synthetic_demo")
    arguments = parser.parse_args()
    result = run_ml_demo(arguments.output)
    for name, value in result.items():
        if isinstance(value, float):
            print(f"{name}={value:.3f}")
        else:
            print(f"{name}={value}")


if __name__ == "__main__":
    main()
