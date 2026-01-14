"""Archived signal processing modules.

This package contains sophisticated algorithms that were developed but are not 
needed for the current project. They are preserved here for potential use in 
future projects.

**NOTE**: The active EMG pipeline code is now in `sensors/` package. This archive
contains historical/alternative implementations.

Modules:
    emg_mvc_hybrid_scoring.py
        Evidence-driven MVC segmentation with multi-threshold scoring system.
        Useful for projects requiring optimal MVC segment detection.
        The active version with the same functionality is now in:
        `sensors.process.emg_mvc.detect_mvc_segments_hybrid()`
        
    emg_mvc_original.py
        Full backup of the original emg_mvc.py before simplification.

Usage Example:
    # For active use, import from sensors package:
    from sensors.process.emg_mvc import detect_mvc_segments_hybrid
    
    # For archived versions (testing/comparison):
    from signal_processing.archive.emg_mvc_hybrid_scoring import detect_mvc_segments_hybrid
"""
