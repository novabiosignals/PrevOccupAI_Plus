"""Utilities for assessing and reporting EMG data quality issues."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Any

import numpy as np
import pandas as pd

from constants import FS_MBAN
from sensors.process.emg_quality_analysis import detect_adc_saturation


# Type aliases for clarity
QualityIssue = Dict[str, str]  # {"code": str, "message": str}
FileQualityReport = Dict[str, Any]  # {"file_path": Path, "issues": List[QualityIssue], ...}


def create_quality_issue(code: str, message: str) -> QualityIssue:
    """Create a quality issue dict."""
    return {"code": code, "message": message}


def create_file_quality_report(
    file_path: Path,
    issues: List[QualityIssue] | None = None,
    rows: int = 0,
    columns: int = 0,
    device_label: str | None = None,
    acquisition_label: str | None = None,
) -> FileQualityReport:
    """Create a file quality report dict."""
    return {
        "file_path": file_path,
        "issues": issues if issues is not None else [],
        "rows": rows,
        "columns": columns,
        "device_label": device_label,
        "acquisition_label": acquisition_label,
    }


def is_report_valid(report: FileQualityReport) -> bool:
    """Check if a report has no issues."""
    return len(report["issues"]) == 0


def add_report_context(
    report: FileQualityReport,
    device: str | None = None,
    acquisition: str | None = None,
) -> FileQualityReport:
    """Add device/acquisition context to a report."""
    if device:
        report["device_label"] = device
    if acquisition:
        report["acquisition_label"] = acquisition
    return report


def describe_report(report: FileQualityReport) -> str:
    """Format report issues as a string."""
    if not report["issues"]:
        return "No issues detected"
    return "; ".join(f"{issue['code']}: {issue['message']}" for issue in report["issues"])


class DataQualityError(RuntimeError):
    """Raised when a file fails the data quality checks and should be skipped."""

    def __init__(self, report: FileQualityReport):
        self.report = report
        message = describe_report(report)
        super().__init__(message)


MIN_MUSCLEBAN_SECONDS = 30
MIN_MUSCLEBAN_SAMPLES = int(FS_MBAN * MIN_MUSCLEBAN_SECONDS)
MIN_MVC_OSCOMPATIBLE_SECONDS = 8
MIN_MVC_OSCOMPATIBLE_SAMPLES = int(FS_MBAN * MIN_MVC_OSCOMPATIBLE_SECONDS)
MAX_ZERO_RATIO = 0.98
MAX_NAN_RATIO = 0.10
MIN_STD_THRESHOLD = 1e-6


def assess_muscleban_dataframe(
    df: pd.DataFrame,
    file_path: Path,
    min_samples: int = MIN_MUSCLEBAN_SAMPLES,
) -> FileQualityReport:
    """Run a series of heuristics to flag unusable recordings.

    :param df: Parsed dataframe straight from disk.
    :param file_path: Source path used only for logging/reporting.
    :param min_samples: Minimum required sample count; defaults to :data:`MIN_MUSCLEBAN_SAMPLES`.
    :returns: Dict containing file path, shape info, and any quality issues found.
    """

    report = create_file_quality_report(file_path=file_path, rows=len(df), columns=df.shape[1])
    if df.empty or df.shape[1] == 0:
        report["issues"].append(create_quality_issue("empty-file", "No samples found after parsing the file."))
        return report

    if min_samples and len(df) < min_samples:
        report["issues"].append(
            create_quality_issue("short-recording", f"Recording has {len(df)} samples (< {min_samples}).")
        )

    emg_cols = [col for col in df.columns if "emg" in str(col).lower()]
    if not emg_cols:
        report["issues"].append(create_quality_issue("missing-emg", "No EMG column found in recording."))
    else:
        emg_values = df[emg_cols[0]].to_numpy(dtype=float)
        finite_mask = np.isfinite(emg_values)
        finite_ratio = finite_mask.mean() if emg_values.size else 0.0
        if finite_ratio < (1 - MAX_NAN_RATIO):
            report["issues"].append(
                create_quality_issue(
                    "too-many-nans",
                    f"Only {finite_ratio:.1%} finite EMG samples (>{MAX_NAN_RATIO:.0%} NaNs).",
                )
            )
        if finite_mask.any():
            finite_values = emg_values[finite_mask]
            zero_ratio = np.mean(np.isclose(finite_values, 0.0)) if finite_values.size else 1.0
            if zero_ratio > MAX_ZERO_RATIO:
                report["issues"].append(
                    create_quality_issue("zero-dominated", f"{zero_ratio:.1%} of EMG samples are ~0 (possible dropout).")
                )
            std_value = float(np.std(finite_values)) if finite_values.size else 0.0
            if std_value < MIN_STD_THRESHOLD:
                report["issues"].append(
                    create_quality_issue("flat-signal", "EMG shows ~0 variance; likely saturated or empty.")
                )
            # Check for ADC saturation/clipping (raw integer values hitting limits)
            saturation_issue = detect_adc_saturation(finite_values)
            if saturation_issue:
                report["issues"].append(saturation_issue)
        else:
            report["issues"].append(create_quality_issue("non-finite", "EMG column contains no finite samples."))

    return report


def summarize_quality_reports(reports: Sequence[FileQualityReport]) -> pd.DataFrame:
    """Return a DataFrame summarizing all collected quality issues.

    :param reports: Sequence of FileQualityReport dicts accumulated during loading.
    :returns: DataFrame listing file path, device, acquisition, shape, and issue summary.
    """

    if not reports:
        return pd.DataFrame(
            columns=["file_path", "device", "acquisition", "rows", "columns", "issues"]
        )

    rows = []
    for report in reports:
        rows.append(
            {
                "file_path": str(report["file_path"]),
                "device": report["device_label"] or "",
                "acquisition": report["acquisition_label"] or "",
                "rows": report["rows"],
                "columns": report["columns"],
                "issues": describe_report(report),
            }
        )

    return pd.DataFrame(rows)


def write_quality_report(reports: Sequence[FileQualityReport], output_path: Path) -> Path:
    """Persist the collected quality issues to *output_path* (CSV).

    :param reports: Sequence of FileQualityReport dicts.
    :param output_path: Destination CSV path (parents created automatically).
    :returns: The provided output path for convenience/chaining.
    """

    df = summarize_quality_reports(reports)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path
