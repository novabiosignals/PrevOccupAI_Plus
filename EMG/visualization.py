import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def visualize_emg_sessions(data_dict, fs=1000):
    """
    Visualizes EMG data for each sensor and session.

    :param data_dict: Dictionary with structure: {'sensor_name': {'session_time': df, ...}, ...}
    :param fs: Sampling frequency in Hz (default: 1000)
    """
    if data_dict is None:
        print("No data to visualize.")
        return

    for sensor_name, sessions in data_dict.items():
        print(f"Visualizing data for {sensor_name}...")
        
        # Sort sessions by time if possible
        sorted_sessions = sorted(sessions.items())
        
        for session_time, df in sorted_sessions:
            plt.figure(figsize=(12, 6))
            
            # Create time axis
            n_samples = len(df)
            time_axis = np.arange(n_samples) / fs
            
            # Identify columns to plot
            # Prioritize 'EMG' column, but plot others if needed (excluding nSeq)
            cols_to_plot = []
            for col in df.columns:
                if 'EMG' in col:
                    cols_to_plot.append(col)
            
            if not cols_to_plot:
                # If no explicit EMG column, plot all numeric columns except nSeq
                cols_to_plot = [col for col in df.columns if col != 'nSeq' and pd.api.types.is_numeric_dtype(df[col])]
            
            for col in cols_to_plot:
                plt.plot(time_axis, df[col], label=col, linewidth=0.8)
            
            plt.title(f"Sensor: {sensor_name} | Session: {session_time}")
            plt.xlabel("Time (s)")
            plt.ylabel("Amplitude (mV)")
            plt.legend(loc='upper right')
            plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
            plt.tight_layout()
            
            # Show the plot
            # Note: This will block execution until the window is closed. 
            # To avoid blocking, one could use plt.show(block=False) and plt.pause(0.1) 
            # but usually for visualization scripts blocking is desired to inspect data.
            plt.show()
