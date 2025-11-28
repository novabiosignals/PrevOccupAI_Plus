from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd


@dataclass(slots=True)
class SessionBundle:
    """Container describing all files needed to process a single EMG session."""

    subject_id: str
    group: int
    device_num: str
    side: str
    mac_address: str
    date: str
    session_label: str
    emg_files: List[Path]
    mvc_file: Path

    @property
    def session_key(self) -> str:
        """Unique key combining date and session label."""

        return f"{self.date}/{self.session_label}"


def discover_session_bundles(
    data_root: str | Path,
    participants_df: pd.DataFrame,
    mvc_keyword: str = "OSCompatible",
) -> list[SessionBundle]:
    """Walk the acquisition folder structure and pair EMG sessions with MVC files.

    The function expects the following hierarchy per subject:
    ``<data_root><group>/sensors/LIBPhys #<device>/<date>/<session_or_MVC>/``

    :param data_root: Base path that ends with "group" (e.g., ``.../data/group``).
    :param participants_df: DataFrame with columns ``device_num``, ``mBAN_left`` and ``mBAN_right``.
    :param mvc_keyword: Filename token that uniquely identifies MVC recordings.
    :return: List of :class:`SessionBundle` objects ready for processing.
    """

    base_path = Path(data_root)
    bundles: list[SessionBundle] = []

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
                    bundles.append(
                        SessionBundle(
                            subject_id=str(subject_id),
                            group=group,
                            device_num=device_num,
                            side=side,
                            mac_address=mac,
                            date=date_label,
                            session_label=session_label,
                            emg_files=emg_files,
                            mvc_file=mvc_file,
                        )
                    )

    return bundles


def _index_mvc_files(mvc_dir: Path, mac_addresses: Iterable[str], mvc_keyword: str) -> Dict[str, Path]:
    """Create a mapping between MAC addresses and MVC files for a given day."""

    mac_set = {mac.strip().lower(): mac.strip() for mac in mac_addresses if mac}
    mapping: Dict[str, Path] = {}

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
    """Gather all EMG files for a session that belong to the provided MAC address."""

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
