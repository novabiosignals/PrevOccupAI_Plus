"""Utilities for assessing and reporting EMG data quality issues."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

import numpy as np
import pandas as pd

from constants import FS_MBAN


@dataclass(slots=True)
class QualityIssue:
    """Represents a single quality finding for a recording."""

    code: str
    message: str


@dataclass(slots=True)
class FileQualityReport:
    """Summary of the checks performed for a given file."""

    file_path: Path
    issues: List[QualityIssue] = field(default_factory=list)
    rows: int = 0
    columns: int = 0
    device_label: str | None = None
    acquisition_label: str | None = None

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def with_context(self, device: str | None, acquisition: str | None) -> "FileQualityReport":
        if device:
            self.device_label = device
        if acquisition:
            self.acquisition_label = acquisition
        return self

    def describe(self) -> str:
        if not self.issues:
            return "No issues detected"
        return "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)


class DataQualityError(RuntimeError):
    """Raised when a file fails the data quality checks and should be skipped."""

    def __init__(self, report: FileQualityReport):
        self.report = report
        message = report.describe()
        super().__init__(message)


MIN_MUSCLEBAN_SECONDS = 30
MIN_MUSCLEBAN_SAMPLES = int(FS_MBAN * MIN_MUSCLEBAN_SECONDS)
MIN_MVC_OSCOMPATIBLE_SECONDS = 8
MIN_MVC_OSCOMPATIBLE_SAMPLES = int(FS_MBAN * MIN_MVC_OSCOMPATIBLE_SECONDS)
MAX_ZERO_RATIO = 0.98
MAX_NAN_RATIO = 0.10
MIN_STD_THRESHOLD = 1e-6


def _issue(code: str, message: str) -> QualityIssue:
    return QualityIssue(code=code, message=message)


def assess_muscleban_dataframe(
    df: pd.DataFrame,
    file_path: Path,
    min_samples: int = MIN_MUSCLEBAN_SAMPLES,
) -> FileQualityReport:
    """Run a series of heuristics to flag unusable recordings.

    :param df: Parsed dataframe straight from disk.
    :param file_path: Source path used only for logging/reporting.
    :param min_samples: Minimum required sample count; defaults to :data:`MIN_MUSCLEBAN_SAMPLES`.
    :returns: Populated :class:`FileQualityReport` that may contain zero or more issues.
    """

    report = FileQualityReport(file_path=file_path, rows=len(df), columns=df.shape[1])
    if df.empty or df.shape[1] == 0:
        report.issues.append(_issue("empty-file", "No samples found after parsing the file."))
        return report

    if min_samples and len(df) < min_samples:
        report.issues.append(
            _issue("short-recording", f"Recording has {len(df)} samples (< {min_samples}).")
        )

    emg_cols = [col for col in df.columns if "emg" in str(col).lower()]
    if not emg_cols:
        report.issues.append(_issue("missing-emg", "No EMG column found in recording."))
    else:
        emg_values = df[emg_cols[0]].to_numpy(dtype=float)
        finite_mask = np.isfinite(emg_values)
        finite_ratio = finite_mask.mean() if emg_values.size else 0.0
        if finite_ratio < (1 - MAX_NAN_RATIO):
            report.issues.append(
                _issue(
                    "too-many-nans",
                    f"Only {finite_ratio:.1%} finite EMG samples (>{MAX_NAN_RATIO:.0%} NaNs).",
                )
            )
        if finite_mask.any():
            finite_values = emg_values[finite_mask]
            zero_ratio = np.mean(np.isclose(finite_values, 0.0)) if finite_values.size else 1.0
            if zero_ratio > MAX_ZERO_RATIO:
                report.issues.append(
                    _issue("zero-dominated", f"{zero_ratio:.1%} of EMG samples are ~0 (possible dropout).")
                )
            std_value = float(np.std(finite_values)) if finite_values.size else 0.0
            if std_value < MIN_STD_THRESHOLD:
                report.issues.append(
                    _issue("flat-signal", "EMG shows ~0 variance; likely saturated or empty.")
                )
        else:
            report.issues.append(_issue("non-finite", "EMG column contains no finite samples."))

    return report


def summarize_quality_reports(reports: Sequence[FileQualityReport]) -> pd.DataFrame:
    """Return a DataFrame summarizing all collected quality issues.

    :param reports: Sequence of :class:`FileQualityReport` objects accumulated during loading.
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
                "file_path": str(report.file_path),
                "device": report.device_label or "",
                "acquisition": report.acquisition_label or "",
                "rows": report.rows,
                "columns": report.columns,
                "issues": report.describe(),
            }
        )

    return pd.DataFrame(rows)


def write_quality_report(reports: Sequence[FileQualityReport], output_path: Path) -> Path:
    """Persist the collected quality issues to *output_path* (CSV).

    :param reports: Sequence of :class:`FileQualityReport` entries.
    :param output_path: Destination CSV path (parents created automatically).
    :returns: The provided output path for convenience/chaining.
    """

    df = summarize_quality_reports(reports)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path
