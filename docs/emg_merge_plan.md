# EMG Pipeline Merge Plan

This note captures which parts of the repository we continue to own for the EMG workflow and which upstream components we will adopt verbatim during the next merge.

## 1. Components we keep (ours wins)

| Area | Reason |
| --- | --- |
| `main_emg.py` | Custom entry point that orchestrates the EMG days, runs effort-bin exports, and logs artifacts. |
| `signal_processing/emg_pipeline.py` + helpers | Contains the end-to-end preprocessing, %MVC normalization, metrics, plots, and effort CSV logic. |
| `emg_analysis/` | Our APDF, metrics, and visualization utilities; tightly coupled to the pipeline above. |
| `docs/*` (EMG mini-book, notes) | Must remain untouched so documentation matches our pipeline. |
| `load_signals/*` + `load_signals/data_quality.py` | Includes OSCompatible MVC logic, filtering tweaks, and docstrings we depend on. |
| `HAR/`, `OH_profile/` | No overlap with upstream refactor; keep existing behavior. |

During merge conflicts in these files, select **ours** (keep current versions) and re-integrate only if we explicitly choose to adopt upstream changes.

## 2. Components we adopt from upstream (theirs wins)

| Area | Reason |
| --- | --- |
| `questionnaires/` tree | Upstream renamed `questionnaire_processing` → `questionnaires` with new loaders/mappings. We are not modifying these files. |
| `main_questionnaires.py` & related configs | Align with upstream naming and structure to avoid drift. |
| IDE configs (`.idea/*`) | No need to preserve ours; accept upstream when conflicts occur. |

## 3. Components to reconcile manually

| Area | Action |
| --- | --- |
| `load_signals` vs `sensors/load` | Upstream moved loader code into `sensors/load`. We keep our package but may later migrate by copying our customizations into the new location. For now, we keep ours and ignore new `sensors/` modules unless we decide to adopt them. |
| `signal_processing` vs `sensors/process` | Same story: upstream introduced `sensors/process`. We retain `signal_processing/` for the EMG pipeline, but note mapping if we eventually port. |
| `main_sensors.py` | New upstream entry point. We can keep it (harmless) while still running `main_emg.py`. |

## 4. Merge checklist

1. **Backup** current branch (done via `git branch emg_premerge_backup`).
2. `git fetch upstream`.
3. `git merge upstream/master`.
4. For each conflict:
   - Files listed in Section 1 ⇒ keep ours.
   - Files in Section 2 ⇒ take theirs.
   - Files in Section 3 ⇒ review diff manually; most likely keep ours now, but log TODOs if we later adopt `sensors/*`.
5. Re-run `python main_emg.py` and confirm artifacts.
6. Inspect new upstream directories (e.g., `questionnaires/`, `sensors/`) and ensure they do not interfere with imports.
7. Commit the merge and push.

## 5. Longer-term refactor idea

If we later want to align with upstream’s `sensors` package, the path is:

1. Move/alias `load_signals` → `sensors/load` while porting OSCompatible MVC logic.
2. Relocate `signal_processing/emg_pipeline.py` under `sensors/process` or expose it via `sensors` namespace.
3. Update `main_emg.py` imports accordingly.
4. Remove duplicate packages once parity is verified.

For now, the plan above preserves a working EMG pipeline while still letting us update from the main project.
