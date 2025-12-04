"""
EMG Filesystem Functions

This module contains functions for discovering and organizing EMG data files:
- Discovering session bundles (pairing EMG files with MVC files)
- Indexing MVC calibration files
- Collecting EMG files for a session

All functions use simple dictionaries instead of classes.
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


# -------------------------------------------------------------------------------------------------------------------- #
# Session Discovery Functions
# -------------------------------------------------------------------------------------------------------------------- #

def discover_session_bundles(
    data_root: str,
    participants_df: pd.DataFrame,
    mvc_keyword: str = "OSCompatible",
) -> List[dict]:
    """
    Walk the acquisition folder structure and pair EMG sessions with MVC files.

    The function expects the following hierarchy per subject:
    <data_root><group>/sensors/LIBPhys #<device>/<date>/<session_or_MVC>/

    :param data_root: Base path that ends with "group" (e.g., .../data/group).
    :param participants_df: DataFrame with columns 'device_num', 'mBAN_left', 'mBAN_right'.
    :param mvc_keyword: Filename token that uniquely identifies MVC recordings.
    :return: List of session bundle dictionaries with keys:
             - subject_id: str
             - group: int
             - device_num: str
             - side: str ('left' or 'right')
             - mac_address: str
             - date: str
             - session_label: str
             - emg_files: list of Path objects
             - mvc_file: Path object
    """
    base_path = Path(data_root)
    bundles = []

    for subject_id, row in participants_df.iterrows():
        group = int(row["group"])
        device_num = str(row["device_num"]).strip()
        subject_path = Path(str(base_path) + str(group)) / "sensors" / f"LIBPhys {device_num}"

        if not subject_path.exists():
            print(f"[discover] Skipping subject {subject_id}: path not found -> {subject_path}")
            continue

        left_mac = str(row.get("mBAN_left", "")).strip()
        right_mac = str(row.get("mBAN_right", "")).strip()

        for date_dir in sorted(p for p in subject_path.iterdir() if p.is_dir()):
            date_label = date_dir.name
            mvc_map = _index_mvc_files(date_dir / "MVC", [left_mac, right_mac], mvc_keyword)

            session_dirs = [p for p in date_dir.iterdir() if p.is_dir() and p.name.upper() != "MVC"]
            for session_dir in sorted(session_dirs):
                session_label = session_dir.name

                for side, mac in (("left", left_mac), ("right", right_mac)):
                    if not mac:
                        continue
                    mvc_file = mvc_map.get(mac)
                    if mvc_file is None:
                        continue
                    emg_files = _collect_emg_files(session_dir, mac)
                    if not emg_files:
                        continue

                    # Create a simple dictionary instead of a dataclass
                    bundle = {
                        "subject_id": str(subject_id),
                        "group": group,
                        "device_num": device_num,
                        "side": side,
                        "mac_address": mac,
                        "date": date_label,
                        "session_label": session_label,
                        "emg_files": emg_files,
                        "mvc_file": mvc_file,
                    }
                    bundles.append(bundle)

    return bundles


def get_session_key(bundle: dict) -> str:
    """
    Get a unique key for a session bundle combining date and session label.

    :param bundle: Session bundle dictionary.
    :return: Key string like '2024-01-15/session_1'.
    """
    return f"{bundle['date']}/{bundle['session_label']}"


# -------------------------------------------------------------------------------------------------------------------- #
# Private Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _index_mvc_files(mvc_dir: Path, mac_addresses: List[str], mvc_keyword: str) -> Dict[str, Path]:
    """
    Create a mapping between MAC addresses and MVC files for a given day.

    :param mvc_dir: Path to the MVC directory for a specific date.
    :param mac_addresses: List of MAC addresses to look for.
    :param mvc_keyword: Keyword that identifies MVC files (e.g., 'OSCompatible').
    :return: Dictionary mapping MAC address to MVC file path.
    """
    mac_set = {mac.strip().lower(): mac.strip() for mac in mac_addresses if mac}
    mapping = {}

    if not mvc_dir.exists():
        return mapping

    for candidate in mvc_dir.glob("*.txt"):
        name_lower = candidate.name.lower()
        if mvc_keyword.lower() not in name_lower:
            continue
        for mac_lower, original_mac in mac_set.items():
            if mac_lower and mac_lower in name_lower:
                mapping[original_mac] = candidate
                break

    return mapping


def _collect_emg_files(session_dir: Path, mac_address: str) -> List[Path]:
    """
    Gather all EMG files for a session that belong to the provided MAC address.

    :param session_dir: Path to the session directory.
    :param mac_address: MAC address to filter files by.
    :return: Sorted list of Path objects for matching EMG files.
    """
    mac_str = str(mac_address).strip()
    if not mac_str:
        return []

    mac_lower = mac_str.lower()
    files = sorted(
        candidate
        for candidate in session_dir.glob("*.txt")
        if mac_lower in candidate.name.lower()
    )

    return files
