import logging
from pathlib import Path
from typing import Callable

import h5py
import numpy as np
from datagen.utils.injection import generate_gw
from typeo import scriptify

from bbhnet.logging import configure_logging


@scriptify
def main(
    prior: Callable,
    n_samples: int,
    reference_frequency: float,
    minimum_frequency: float,
    sample_rate: float,
    waveform_duration: float,
    waveform_approximant: str,
    logdir: Path,
    datadir: Path,
    force_generation: bool = False,
    verbose: bool = False,
):
    """Simulates a set of raw BBH signals and saves them to an output file.

    Args:
        prior: function returning a bilby PriorDict for bilby to sample from
        n_samples: number of signals to simulate
        reference_frequency: reference frequency for waveform generation
        minimum_frequency: minimum frequency for waveform generation
        sample_rate: sample rate of the simulated signals
        waveform_duration: length of injected waveforms in seconds
        waveform_approximant: which lalsimulation waveform approximant to use
        logdir: directory where log file will be written
        datadir: output directory to which signals will be written
        force_generation: if True, generate signals even if path already exists
        verbose: log verbosely
    """

    # make dirs
    datadir.mkdir(exist_ok=True, parents=True)
    logdir.mkdir(exist_ok=True, parents=True)

    configure_logging(logdir / "generate_waveforms.log", verbose)

    # check if signal file already exists
    signal_file = datadir / "signals.h5"

    if signal_file.exists() and not force_generation:
        logging.info(
            "Signal data already exists and forced generation is off. "
            "Not generating signals."
        )
        return signal_file

    # log and print out some simulation parameters
    logging.info("Simulation parameters")
    logging.info("Number of samples     : {}".format(n_samples))
    logging.info("Sample rate [Hz]      : {}".format(sample_rate))
    logging.info("Prior name            : {}".format(prior.__name__))

    # sample gw parameters from prior distribution
    priors = prior()
    sample_params = priors.sample(n_samples)

    signals = generate_gw(
        sample_params,
        minimum_frequency,
        reference_frequency,
        sample_rate,
        waveform_duration,
        waveform_approximant,
    )

    # Write params and similar to output file
    if np.isnan(signals).any():
        raise ValueError("The signals contain NaN values")

    with h5py.File(signal_file, "w") as f:
        # write signals attributes, snr, and signal parameters
        for k, v in sample_params.items():
            f.create_dataset(k, data=v)

        f.create_dataset("signals", data=signals)

        # write attributes
        f.attrs.update(
            {
                "size": n_samples,
                "sample_rate": sample_rate,
                "waveform_duration": waveform_duration,
                "waveform_approximant": waveform_approximant,
                "reference_frequency:": reference_frequency,
                "minimum_frequency": minimum_frequency,
            }
        )

    return signal_file


if __name__ == "__main__":
    main()
