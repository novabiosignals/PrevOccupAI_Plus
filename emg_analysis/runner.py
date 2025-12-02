from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from sensors.load.meta_data import load_meta_data
from utils import create_dir

from .filesystem import SessionBundle, discover_session_bundles
from .metrics import (APDFResult, aggregate_daily_metrics, compute_percentage_changes,
                      compute_session_metrics)
from .preprocessing import process_session
from .visuals import (plot_apdf, plot_histogram, plot_metric_series,
                      plot_session_effort_grid, plot_session_effort_session_stacks)


def run_emg_analysis(
    data_folder: str,
    results_folder: str,
    plot_folder: str,
    participants_csv: str = "participants_info.csv",
    generate_visuals: bool = True,
    subject_filter: list[str] | None = None,
) -> None:
    """Entry point that ties together loading, processing, metrics, and plots."""

    meta_df = load_meta_data(participants_csv)
    if subject_filter:
        allowed = {str(s).strip() for s in subject_filter if str(s).strip()}
        meta_df = meta_df.loc[meta_df.index.map(lambda idx: str(idx) in allowed)]
        if meta_df.empty:
            print("[EMG analysis] Subject filter yielded no matches. Aborting.")
            return
    bundles = discover_session_bundles(data_folder, meta_df)

    if not bundles:
        print("[EMG analysis] No sessions discovered. Aborting.")
        return

    analysis_root = create_dir(results_folder, "emg_analysis")
    plots_root = create_dir(plot_folder, "emg_analysis")
    tables_root = create_dir(analysis_root, "tables")

    session_records: list[dict] = []
    apdf_payloads: list[tuple[SessionBundle, APDFResult, float]] = []

    for bundle in bundles:
        try:
            percent_signal, fs, mvc_peak = process_session(bundle.emg_files, bundle.mvc_file)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[EMG analysis] Failed processing {bundle.session_key} ({bundle.side}): {exc}")
            continue

        metadata = {
            "subject_id": bundle.subject_id,
            "group": bundle.group,
            "device_num": bundle.device_num,
            "side": bundle.side,
            "mac_address": bundle.mac_address,
            "date": bundle.date,
            "session_label": bundle.session_label,
            "mvc_peak": mvc_peak,
            "fs_hz": fs,
        }
        metrics, apdf_result = compute_session_metrics(percent_signal, fs, metadata)
        session_records.append(metrics)
        apdf_payloads.append((bundle, apdf_result, fs))

    session_df = pd.DataFrame(session_records)
    if session_df.empty:
        print("[EMG analysis] No valid sessions produced metrics.")
        return

    value_cols = [
        "iemg_percent_seconds",
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
    ]

    daily_df = aggregate_daily_metrics(session_df, value_cols)

    session_increments = compute_percentage_changes(
        session_df,
        group_cols=["subject_id", "side", "date"],
        order_col="session_label",
        value_cols=["iemg_percent_seconds", "apdf_p50"],
        label="session",
    )

    daily_increments = compute_percentage_changes(
        daily_df,
        group_cols=["subject_id", "side"],
        order_col="date",
        value_cols=["iemg_percent_seconds", "apdf_p50"],
        label="day",
    )

    Path(tables_root, "session_metrics.csv").write_text(session_df.to_csv(index=False), encoding="utf-8")
    Path(tables_root, "daily_metrics.csv").write_text(daily_df.to_csv(index=False), encoding="utf-8")
    Path(tables_root, "session_increments.csv").write_text(session_increments.to_csv(index=False), encoding="utf-8")
    Path(tables_root, "daily_increments.csv").write_text(daily_increments.to_csv(index=False), encoding="utf-8")

    if not generate_visuals:
        return

    plot_root_path = Path(plots_root)
    day_payloads: dict[tuple[str, str], dict[tuple[str, str], tuple[np.ndarray, float]]] = defaultdict(dict)
    for bundle, apdf, fs in apdf_payloads:
        session_dir = plot_root_path / bundle.subject_id / bundle.side / bundle.date
        apdf_path = session_dir / f"{bundle.session_label}_apdf.png"
        hist_path = session_dir / f"{bundle.session_label}_hist.png"
        title = f"{bundle.subject_id} | {bundle.side} | {bundle.date} {bundle.session_label}"
        plot_apdf(apdf, apdf_path, title)
        plot_histogram(apdf.amplitudes, hist_path, f"Histogram – {title}")
        key = (bundle.subject_id, bundle.date)
        day_payloads[key][(bundle.side, bundle.session_label)] = (apdf.amplitudes, fs)

    for (subject_id, date), payload in day_payloads.items():
        session_labels = sorted({session_label for (_, session_label) in payload.keys()})
        if not session_labels:
            continue
        day_dir = plot_root_path / subject_id / date
        output_path = day_dir / "effort_distribution.png"
        plot_session_effort_grid(payload, session_labels, output_path, f"{subject_id} – {date}")
        stacks_path = day_dir / "effort_distribution_sessions.png"
        plot_session_effort_session_stacks(payload, session_labels, stacks_path,
                           f"{subject_id} – {date} session progression")

    # Plot increments per subject/side/day for sessions
    if not session_increments.empty:
        for (subject_id, side, date), group_df in session_increments.groupby(["subject_id", "side", "date"]):
            for metric in ("iemg_percent_seconds", "apdf_p50"):
                change_col = f"session_{metric}_pct_change"
                if change_col not in group_df:
                    continue
                output = plot_root_path / subject_id / side / date / f"session_change_{metric}.png"
                plot_metric_series(group_df, change_col, "session_label", output,
                                   f"Session Δ {metric} – {subject_id} {side} {date}")

    if not daily_increments.empty:
        for (subject_id, side), group_df in daily_increments.groupby(["subject_id", "side"]):
            for metric in ("iemg_percent_seconds", "apdf_p50"):
                change_col = f"day_{metric}_pct_change"
                if change_col not in group_df:
                    continue
                output = plot_root_path / subject_id / side / f"daily_change_{metric}.png"
                plot_metric_series(group_df, change_col, "date", output,
                                   f"Daily Δ {metric} – {subject_id} {side}")
