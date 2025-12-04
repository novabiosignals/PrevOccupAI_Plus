from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from constants import MBAN
from .meta_data import load_meta_data
from .daily_data_loader import load_daily_acquisitions
from .data_quality import FileQualityReport


def discover_daily_acquisitions(
    data_root: str | Path,
    participants_csv: str | Path = "participants_info.csv",
    subject_filter: Optional[Sequence[str]] = None,
    max_subjects: Optional[int] = None,
    max_days_per_subject: Optional[int] = None,
) -> List[dict]:
    """Walk the acquisition tree and list every available subject/day folder.

    :param data_root: Base folder containing the ``groupX`` directories.
    :param participants_csv: CSV exported from LimeSurvey that maps subject metadata → filesystem layout.
    :param subject_filter: Optional whitelist of subject identifiers.
    :param max_subjects: Limit the number of unique subjects to include; useful for smoke tests.
    :param max_days_per_subject: Cap the number of day folders per subject.
    :returns: List of dicts with keys: subject_id, group, device_num, day_path, left_mac, right_mac, date_label, subject_root.
    """

    base_path = Path(data_root)
    meta_df = load_meta_data(participants_csv)

    allowed_subjects = None
    if subject_filter:
        allowed_subjects = {str(item).strip() for item in subject_filter if str(item).strip()} 

    day_descriptors: List[dict] = []
    subjects_seen: set[str] = set()

    for subject_id, row in meta_df.iterrows():
        subject_key = str(subject_id)
        if allowed_subjects and subject_key not in allowed_subjects:
            continue
        if max_subjects is not None and len(subjects_seen) >= max_subjects and subject_key not in subjects_seen:
            break

        group = int(row["group"])
        device_num = str(row["device_num"]).strip()
        left_mac = str(row.get("mBAN_left", "")).strip()
        right_mac = str(row.get("mBAN_right", "")).strip()

        # Build the expected filesystem path for this subject. Each subject gets their own folder
        # inside ``groupX/sensors``.
        subject_root = base_path / f"group{group}" / "sensors" / f"LIBPhys {device_num}"
        if not subject_root.exists():
            print(f"[dataset_loader] Subject {subject_id}: folder not found -> {subject_root}")
            continue

        day_dirs = sorted(path for path in subject_root.iterdir() if path.is_dir())
        if max_days_per_subject is not None:
            day_dirs = day_dirs[:max_days_per_subject]

        if not day_dirs:
            continue

        subjects_seen.add(subject_key)

        for day_path in day_dirs:
            day_descriptors.append({
                "subject_id": subject_key,
                "group": group,
                "device_num": device_num,
                "day_path": day_path,
                "left_mac": left_mac,
                "right_mac": right_mac,
                "date_label": day_path.name,
                "subject_root": day_path.parent,
            })

    return day_descriptors


def load_day_acquisitions(
    day_descriptor: dict,
    selected_sensors: Optional[Dict[str, List[str]]] = None,
    quality_log: Optional[List[FileQualityReport]] = None,
):
    """Wrapper around :func:`load_daily_acquisitions` that keeps metadata alongside the data.

    :param day_descriptor: Dict with keys: subject_id, group, device_num, day_path, left_mac, right_mac, date_label.
    :param selected_sensors: Optional mapping of devices to sensor names to load.
    :param quality_log: Optional list that will be extended with :class:`FileQualityReport` entries.
    :returns: Nested dict structured ``device -> acquisition_label -> DataFrame``.
    """

    if selected_sensors is None:
        selected_sensors = {MBAN: ["EMG"]}
    return load_daily_acquisitions(
        str(day_descriptor["day_path"]),
        selected_sensors,
        quality_log=quality_log,
    )
