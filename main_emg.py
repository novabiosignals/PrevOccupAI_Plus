"""Orchestrate the EMG cohort processing pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from constants import MBAN
from sensors.load.data_quality import FileQualityReport
from sensors.load.dataset_loader import discover_daily_acquisitions
from signal_processing import PreprocessConfig, run_emg_pipeline

# ------------------------------------------------------------------------------------------------------------------- #
# Configuration
# ------------------------------------------------------------------------------------------------------------------- #
DATA_ROOT = Path(r"C:\Users\gonba\PrevOccupAI_plus_Data\data")
PARTICIPANTS_CSV = Path("participants_info.csv")
SELECTED_SENSORS = {MBAN: ["EMG"]}
RESULTS_ROOT = Path("results") / "emg_pipeline"
PLOTS_ROOT = RESULTS_ROOT / "plots"
DEFAULT_CONFIG = PreprocessConfig()


def _ensure_data_root() -> None:
    """Safeguard pipeline execution by validating that the raw data directory exists."""

    # Centralized guard so every entry-point call benefits from the same friendly error.
    if not DATA_ROOT.exists():
        raise FileNotFoundError(
            f"DATA_ROOT='{DATA_ROOT}' is not available. Update the path in main_emg.py before running the pipeline."
        )


def build_day_index(
    subject_filter: Sequence[str] | None = None,
    max_subjects: int | None = None,
    max_days_per_subject: int | None = None,
) -> list[dict]:
    """Gather candidate acquisitions that satisfy the user-selected filters.

    :param subject_filter: Optional iterable with explicit subject identifiers to include.
    :param max_subjects: Hard upper bound for the number of subjects to enumerate.
    :param max_days_per_subject: Maximum number of day folders per subject to process.
    :returns: List of dicts describing subject, day, and device routing.
    """

    _ensure_data_root()
    descriptors = discover_daily_acquisitions(
        DATA_ROOT,
        participants_csv=PARTICIPANTS_CSV,
        subject_filter=subject_filter,
        max_subjects=max_subjects,
        max_days_per_subject=max_days_per_subject,
    )

    unique_subjects = {descriptor["subject_id"] for descriptor in descriptors}
    print(
        f"[main_emg] Discovered {len(descriptors)} day folders across {len(unique_subjects)} subjects."
    )
    return descriptors


def main(
    run_all: bool = False,
    load_data: bool = False,
    preprocess: bool = False,
    visualize: bool = False,
    subject_filter: Sequence[str] | None = None,
    max_subjects: int | None = None,
    max_days_per_subject: int | None = None,
):
    """Coordinate dataset discovery, preprocessing, and visualization stages.

    This entry point intentionally mirrors the legacy CLI switches exposed to analysts so that
    scripts and notebooks can reuse the same logic programmatically.

    :param run_all: Convenience flag that enables loading, preprocessing, and visualizations in one go.
    :param load_data: Whether to enumerate the filesystem and build the day descriptors list.
    :param preprocess: Set to ``True`` to actually run the pipeline beyond discovery.
    :param visualize: Toggles plotting so heavy plotting can be skipped during smoke tests.
    :param subject_filter: Optional whitelist of subject identifiers to include.
    :param max_subjects: Upper bound for subject count, handy for quick subset checks.
    :param max_days_per_subject: Upper bound for day folders per subject.
    :returns: Mapping of artifact labels to filesystem paths for anything produced by the run.
    """

    if run_all:
        load_data = preprocess = visualize = True

    descriptors: list[dict] = []

    # The underlying data loader is relatively heavy, so only run it when a later stage needs the result.
    if load_data or preprocess:
        descriptors = build_day_index(subject_filter, max_subjects, max_days_per_subject)
        if not descriptors:
            print("[main_emg] No acquisitions found. Nothing to do.")
            return None

    if not preprocess:
        print("[main_emg] Preprocessing skipped (preprocess flag is False).")
        return None

    print("[main_emg] Starting EMG pipeline...")
    quality_reports: list[FileQualityReport] = []
    artifacts = run_emg_pipeline(
        descriptors,
        selected_sensors=SELECTED_SENSORS,
        results_root=RESULTS_ROOT,
        plots_root=PLOTS_ROOT,
        config=DEFAULT_CONFIG,
        generate_visuals=visualize,
        quality_log=quality_reports,
    )

    print("[main_emg] Pipeline finished. Artifacts:")
    for label, path in artifacts.items():
        print(f"    - {label}: {path}")

    if quality_reports:
        report_path = artifacts.get("quality_report")
        if report_path:
            print(
                f"[main_emg] {len(quality_reports)} acquisition(s) skipped due to data quality. "
                f"See {report_path} for details."
            )
        else:
            print(f"[main_emg] {len(quality_reports)} acquisition(s) failed data-quality checks.")

    return artifacts


if __name__ == '__main__':
    main(run_all=True)




