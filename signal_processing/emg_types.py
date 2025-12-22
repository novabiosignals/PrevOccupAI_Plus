"""Shared type definitions for EMG signal processing modules.

This module provides type aliases and type definitions used across
the signal_processing package to avoid circular imports.
"""

from typing import Any, Dict

# Type alias for preprocessing configuration dictionary.
# Keys typically include: fs, lowcut, highcut, smooth_sigma_ms, envelope_preview_seconds
PreprocessConfig = Dict[str, Any]
