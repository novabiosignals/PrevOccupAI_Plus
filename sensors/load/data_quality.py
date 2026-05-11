"""Utilities for assessing and reporting EMG data quality issues."""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Any
import numpy as np
import pandas as pd

# internal imports
from constants import FS_MBAN, EMG
from sensors.process.emg_quality_analysis import detect_adc_saturation

# -------------------------------------------------------------------------------------------------------------------- #
# type definitions
# -------------------------------------------------------------------------------------------------------------------- #
# Type aliases for clarity
QualityIssue = Dict[str, str]  # {"code": str, "message": str}
FileQualityReport = Dict[str, Any]  # {"file_path": Path, "issues": List[QualityIssue], ...}

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
MIN_MUSCLEBAN_SECONDS = 30
MIN_MUSCLEBAN_SAMPLES = int(FS_MBAN * MIN_MUSCLEBAN_SECONDS)
MIN_MVC_OSCOMPATIBLE_SECONDS = 8
MIN_MVC_OSCOMPATIBLE_SAMPLES = int(FS_MBAN * MIN_MVC_OSCOMPATIBLE_SECONDS)
MAX_ZERO_RATIO = 0.98
MAX_NAN_RATIO = 0.10
MIN_STD_THRESHOLD = 1e-6

# FileQualityReport keys
FILE_PATH_KEY = "file_path"
ISSUES_KEY = "issues"
ROWS_KEY = "rows"
COLS_KEY = "columns"
DEVICE_LABEL_KEY = "device_label"
ACQUISITION_LABEL_KEY = "acquisition_label"

# QualityIssue keys
CODE_KEY = "code"
MESSAGE_KEY = "message"

# -------------------------------------------------------------------------------------------------------------------- #
# public class for raising muscleBAN data quality issues
# -------------------------------------------------------------------------------------------------------------------- #
class DataQualityError(RuntimeError):
    """Raised when a file fails the data quality checks and should be skipped."""

    def __init__(self, report: FileQualityReport):
        self.report = report
        message = describe_report(report)
        super().__init__(message)

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #
def create_quality_issue(code: str, message: str) -> QualityIssue:
    """
    Create a quality issue. These issues can be appended to a FileQualityReport
    :param code: the quality issue code
    :param message: message to write to the quality issue
    :return: Dict containing the quality issue
    """
    """Create a quality issue dict."""
    return {CODE_KEY: code, MESSAGE_KEY: message}


def create_file_quality_report(file_path: Path, issues: List[QualityIssue] | None = None,
                               rows: int = 0, columns: int = 0,
                               device_label: str | None = None, acquisition_label: str | None = None) -> FileQualityReport:
    """
    Creates a file quality report to store quality issues while loading/processing the data. The function can be used
    to create an empty report that is populated at a later stage.
    :param file_path: the file path of the file for which the quality report should be created
    :param issues: the issues to report in the form a QualityIssue.
    :param rows: the number of rows the file contains
    :param columns: the number of columns the file contains
    :param device_label: the device label. Either 'mBAN_left' or 'mBAN_right'.
    :param acquisition_label: the acquisition time-stamp or label.
    :return:
    """

    return {
        FILE_PATH_KEY: file_path,
        ISSUES_KEY: issues if issues is not None else [],
        ROWS_KEY: rows,
        COLS_KEY: columns,
        DEVICE_LABEL_KEY: device_label,
        ACQUISITION_LABEL_KEY: acquisition_label,
    }


def report_contains_issues(report: FileQualityReport) -> bool:
    """
    Utility wrapper to check whether the report has no issues
    :param report: a FileQualityReport object
    :return: boolean indicating whether the report has no issues.
    """
    return len(report["issues"]) != 0


def write_info_to_report(report: FileQualityReport, issue: QualityIssue | None = None,
                         device_label: str | None = None, acquisition_label: str | None = None) -> FileQualityReport:
    """
    Add device and acquisition info to the FileQualityReport.
    :param report: the FileQualityReport into which the information shouldbe written to.
    :param issue: the issues to report in the form a QualityIssue.
    :param device_label: the device label. Either 'mBAN_left' or 'mBAN_right'.
    :param acquisition_label: the acquisition time-stamp or label.
    :return: the updated report
    """

    if issue is not None:
        report[ISSUES_KEY].append(issue)

    if device_label is not None:
        report[DEVICE_LABEL_KEY] = device_label

    if acquisition_label is not None:
        report[ACQUISITION_LABEL_KEY] = acquisition_label

    return report


def assess_mban_data_validity(mban_df: pd.DataFrame, file_path: Path) -> FileQualityReport:
    """
    Assesses the quality of the muscleBAN by performing the following checks
    (1) empty file: the muscleBAN file is empty
    (2): minimum samples size: the data is checked whether it contains enough samples to be viable for further processing
    (3)...still need to add the following steps

    :param mban_df: Parsed dataframe straight from disk.
    :param file_path: Source path used only for logging/reporting.
    :returns: Dict containing file path, shape info, and any quality issues found.
    """

    # generate FileQualityReport to log data quality issues
    report = create_file_quality_report(file_path=file_path, rows=len(mban_df), columns=mban_df.shape[1])

    # (1) empty file after loading (e.g., the file had only a header)
    if mban_df.empty or mban_df.shape[1] == 0:
        write_info_to_report(report=report, issue=create_quality_issue("empty-file", "No samples found after parsing the file."))

        # return report immediately as there is nothing more to be checked
        return report

    # (2) minimum samples size
    # get the minimum amount of viable samples depending on the file
    min_samples = _get_muscleban_min_samples(file_path)
    if len(mban_df) < min_samples:
        write_info_to_report(report=report, issue=create_quality_issue("short-recording", f"Recording has {len(mban_df)} samples (< {min_samples})."))

    # (3) check for nan or +inf, -inf values
    # transform EMG data into numpy array
    emg_array = mban_df[EMG].to_numpy(dtype=float)

    # (4) check for saturation


    # this check is not necessary. The case will never happen
    emg_cols = [col for col in mban_df.columns if "emg" in str(col).lower()]
    if not emg_cols:
        report["issues"].append(create_quality_issue("missing-emg", "No EMG column found in recording."))
    else:
        emg_values = mban_df[emg_cols[0]].to_numpy(dtype=float)
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

# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #
def _get_muscleban_min_samples(file_path: Path) -> float:
    """
    gets the minimum amount of viable samples for the file to be considered
    :param file_path: pathlib.Path to the folder containing the file.
    :return: the minimum number of samples required for the file to be considered
    """

    # obtain the folder name in which the file is located
    acquisition_folder = file_path.parent.name.strip().upper()

    # obtain the file name
    file_name = file_path.stem.upper()

    # check whether the folder and the file belong to an MVC file
    is_oscompatible_mvc = acquisition_folder == "MVC" and "OSCOMPATIBLE" in file_name

    # return the right amount of minimum samples
    return MIN_MVC_OSCOMPATIBLE_SAMPLES if is_oscompatible_mvc else MIN_MUSCLEBAN_SAMPLES





def describe_report(report: FileQualityReport) -> str:
    """Format report issues as a string."""
    if not report["issues"]:
        return "No issues detected"
    return "; ".join(f"{issue['code']}: {issue['message']}" for issue in report["issues"])









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
