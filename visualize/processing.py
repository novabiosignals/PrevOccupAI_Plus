"""
Functions for detecting noisy signals and, if possible, recover them.

Available Functions
-------------------
[Public]
plot_emg_preprocess(emg_signal, title, plot_folder): plots the signal at any stage of the pre-processing process
plot_psd_noise_detection(psd_freqs, psd, x_peaks, y_peaks, title, plot_folder): plots the detected peaks in the PSD.
plot_psd(psd, freqs, title, plot_folder): plots the power spectral density function
plot_walk_detector_output(acc_df, preds, subject_info, plot_folder): plots the accelerometer data together with the output of the walk detector model.
plot_envelope(emg_series, envelope_series, title, plot_folder): function to plot the EMG together with its envelope
plot_df_data(df, title, plot_folder, x_label, y_label):  plots the data of an entire dataframe into a single plot and saves it in the specified plot folder
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import matplotlib.pyplot as plt
import os
import pandas as pd


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def plot_emg_preprocess(emg_signal, title, plot_folder):
    """
    plots the signal at any stage of the pre-processing process.
    :param emg_signal: the emg_signal (either pandas series, numpy array, or list)
    :param title: the title of the plot as string
    :param plot_folder: path to the folder where the plots should be stored
    :return: no return
    """

    # check if the signal is not yet a pandas series
    if not isinstance(emg_signal, pd.core.series.Series):

        # check if it is an empty dataframe
        if isinstance(emg_signal, pd.DataFrame):

            if emg_signal.empty:
                print('empty dataframe nothing to plot')
                return

            else:
                emg_signal = emg_signal.squeeze()

        else:
            # cast it to as series
            emg_signal = pd.Series(emg_signal)

    # plot the signal
    fig = emg_signal.plot(kind='line', title=title).get_figure()  # .savefig(save_path + title + '.png')
    plt.xlabel("samples [n]")
    plt.ylabel("EMG [mV]")
    # save the figure
    fig.get_figure().savefig(os.path.join(plot_folder, title + '.png'))

    plt.close(fig)


def plot_psd_noise_detection(psd_freqs, psd, x_peaks, y_peaks, title, plot_folder):
    """
    plots the detected peaks in the PSD. This serves as a tool to evaluate the noise detection output
    :param psd_freqs: the PSD frequencies
    :param psd: the PSD values
    :param x_peaks: the x values of the detected peaks
    :param y_peaks: the y values of the detected peaks
    :param title: the figure title
    :param plot_folder: path to the folder where the plots should be stored
    :return: none
    """
    # create figure
    plt.figure()

    # plot the psd
    plt.plot(psd_freqs, psd)

    # plot the deteced peaks
    plt.plot(x_peaks, y_peaks, 'rx', markersize=8)

    # add labels and title
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Power spectral density [Normalized]')
    plt.title(title)

    # save and close figure
    plt.savefig(os.path.join(plot_folder, title + '.png'))
    plt.close()


def plot_psd(psd, freqs, title, plot_folder):
    """
    plots the power spectral density function
    :param psd: power spectral density
    :param freqs: sample frequencies
    :param title: plot title
    :param plot_folder: the folder where the plots should be stored
    :return: none
    """

    # create figure
    plt.figure(figsize=(12, 5))

    # create title
    plt.title('PSD_' + title)

    # plot power spectral density
    plt.plot(freqs, psd, lw=2)

    # add labels
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Power spectral density [mV^2 / Hz]')

    # save and close figure
    plt.savefig(os.path.join(plot_folder, title + '.png'))
    plt.close()


def plot_walk_detector_output(acc_df, preds, subject_info, plot_folder):
    """
    plots the accelerometer data together with the output of the walk detector model.
    :param acc_df: pd.DataFrame containing the accelerometer data
    :param preds: the predicition output of the walk detector model
    :param subject_info: the subject info as a string. This string consists of the subject ID,
                         the muscleBAN mac address, and the date and time of the acquisition
    :param plot_folder: path to the folder where the plots should be stored
    :return: none
    """
    # plot the prediction output against the zAcc axis
    fig = plt.figure()
    title = "Classification result mban_" + subject_info
    plt.title(title)
    plt.plot(acc_df['timestamp'].values, acc_df['zAcc'].values, label='zAcc')
    plt.plot(acc_df['timestamp'].values, preds, label='classification')
    plt.xlabel("time [s]")
    plt.ylabel("m/s^2 | model output (scaled to acc signal)")

    # save and close the figure
    plt.savefig(os.path.join(plot_folder, title + '.png'))
    plt.close(fig)


def plot_envelope(emg_series, envelope_series, title, plot_folder):
    """
    function to plot the EMG together with its envelope
    :param emg_series: pd.Series() of the EMG
    :param envelope_series: pd.Series
    :param title: the plot title
    :param plot_folder: path to the folder where the plots should be stored
    :return: none
    """

    # create figure
    plt.figure(figsize=(12, 5))

    # create title
    plt.title('Envelope_' + title)

    # plot the original emg series and the envelope
    plt.plot(emg_series, color='cornflowerblue', lw=2.0)
    plt.plot(envelope_series, color='orange', lw=1.0)

    # add labels
    plt.xlabel('Samples [n]')
    plt.ylabel('EMG [mV]')

    # save and close figure
    plt.savefig(os.path.join(plot_folder, title + '.png'))
    plt.close()


def plot_df_data(df, title, plot_folder, x_label, y_label):
    """
    plots the data of an entire dataframe into a single plot and saves it in the specified plot folder
    :param df: a dataframe containing data
    :param title: the title of the plot
    :param plot_folder: the folder where the plots should be stored
    :param x_label: the x label as a string
    :param y_label: the y label as a string
    :return: none
    """
    # plot the data
    fig = df.plot(kind='line', title=title, xlabel=x_label, ylabel=y_label).get_figure()

    # save the figure and close it
    fig.get_figure().savefig(os.path.join(plot_folder, title + '.png'))
    plt.close(fig)

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
