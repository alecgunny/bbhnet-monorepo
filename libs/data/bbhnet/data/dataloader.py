from typing import Optional

import h5py
import numpy as np
import torch
from gwpy.filter_design import fir_from_transfer
from scipy import signal

DEFAULT_FFTLENGTH = 2


def _build_filter(timeseries: np.ndarray, sample_rate: float):
    nfft = int(DEFAULT_FFTLENGTH * sample_rate)
    asd = (
        signal.welch(
            timeseries,
            fs=sample_rate,
            nperseg=nfft,
            scaling="density",
            average="median",
        )
        ** 0.5
    )
    return fir_from_transfer(1 / asd, ntaps=nfft, window="hanning", ncorner=0)


class RandomWaveformDataset:
    def __init__(
        self,
        hanford_background: str,
        livingston_background: str,
        kernel_length: float,
        sample_rate: float,
        batch_size: int,
        batches_per_epoch: int,
        waveform_dataset: Optional[str] = None,
        waveform_frac: float = 0,
        glitch_dataset: Optional[str] = None,
        glitch_frac: float = 0,
        device: torch.device = "cuda",
    ) -> None:
        # sanity check our fractions
        assert 0 <= waveform_frac <= 1
        assert 0 <= glitch_frac <= 1

        # this one actually won't be sufficient:
        # e.g. if they add up to 0.99 but our batch
        # size is 32, they still won't leave any room
        # for background
        assert (waveform_frac + glitch_frac) <= 1

        # load in the background data
        # TODO: maybe these are gwf and we resample?
        with h5py.File(hanford_background, "r") as f:
            hanford_bkgrd = f["hoft"][:]
            hanford_filter = _build_filter(hanford_bkgrd, sample_rate)

            # move everything onto the GPU up front so that
            # we don't have to pay for transfer time later.
            # If our datasets are on the scale of ~GBs this
            # shouldn't be a problem, esp. for the current
            # size of BBHNet
            self.hanford_background = torch.Tensor(hanford_bkgrd).to(device)
        with h5py.File(livingston_background, "r") as f:
            livingston_bkgrd = f["hoft"][:]
            livingston_filter = _build_filter(livingston_bkgrd, sample_rate)
            self.livingston_background = torch.Tensor(livingston_bkgrd).to(
                device
            )

        self.whitening_filter = np.stack([hanford_filter, livingston_filter])[
            :, None
        ]
        self.whitening_scale = np.sqrt(2 / sample_rate)

        # ensure that we have the same amount of
        # data from both detectors
        assert len(self.hanford_background) == len(self.livingston_background)

        # load in any waveforms if we specified them
        # TODO: what will the actual field name be?
        # TODO: will these need to be resampled?
        if waveform_dataset is not None:
            assert waveform_frac > 0
            with h5py.File(waveform_dataset, "r") as f:
                # should have shape:
                # (num_waveforms, 2, sample_rate * num_seconds)
                # where 2 is for each detector and num_seconds
                # is however long we had bilby make the waveforms
                self.waveforms = torch.Tensor(f["waveforms"][:]).to(device)
        else:
            assert waveform_frac == 0
            self.waveforms = None

        # load in any glitches if we specified them
        # TODO: what will the actual field name be?
        # TODO: will these need to be resampled?
        if glitch_dataset is not None:
            assert glitch_frac > 0
            with h5py.File(glitch_dataset, "r") as f:
                self.hanford_glitches = f["hanford"][:]
                self.livingston_glitches = f["livingston"]
        else:
            assert glitch_frac == 0
            self.glitches = None

        # TODO: do we want to use these as max fractions
        # and sample the actual number randomly at loading time?
        self.num_waveforms = int(self.waveform_frac * batch_size)
        self.num_glitches = int(self.glitch_frac * batch_size)

        self.kernel_size = int(kernel_length * sample_rate)
        self.batch_size = batch_size
        self.batches_per_epoch = batches_per_epoch

    def __iter__(self):
        self._batch_idx = 0
        return self

    def sample_from_array(self, array, N):
        # do this all with numpy for now to avoid data transfer
        # sample a bunch of indices of samples to grab
        idx = np.random.choice(len(array), size=N, replace=False)

        # for each index, grab a random kernel-sized
        # stretch of the sampled timeseries
        # TODO: is there a good way to do this with array ops?
        samples = []
        for i in idx:
            start = np.random.randint(array.shape[-1] - self.kernel_size)
            stop = start + self.kernel_size
            if len(array.shape) == 2:
                samples.append(array[i, start:stop])
            else:
                samples.append(array[i, :, start:stop])

        # return the list of samples
        return samples

    def sample_from_background(self, independent: bool = True):
        hanford_start = np.random.choice(
            len(self.hanford_background) - self.kernel_size,
            size=self.batch_size,
            replace=False,
        )
        if independent:
            livingston_start = np.random.choice(
                len(self.livingston_background) - self.kernel_size,
                size=self.batch_size,
                replace=False,
            )
        else:
            livingston_start = hanford_start

        # TODO: is there a good way to do this with array ops?
        X = []
        for h_idx, l_idx in zip(hanford_start, livingston_start):
            hanford = self.hanford_background[h_idx : h_idx + self.kernel_size]
            livingston = self.livingston_background[
                l_idx : l_idx + self.kernel_size
            ]
            X.append([hanford, livingston])

        # TODO: not sure torch will like that you're
        # cat-ing lists of lists. Will stack work?
        return torch.cat(X, axis=0)

    def inject_waveforms(self, background, waveforms):
        # TODO: what does this look like?
        raise NotImplementedError

    def whiten(self, X: torch.Tensor) -> torch.Tensor:
        X = X - X.mean(axis=-1)
        X = torch.functional.conv1d(
            X, self.whitening_filter, groups=2, padding="same"
        )
        return X * self.whitening_scale

    def __next__(self):
        if self._batch_idx >= self.batches_per_epoch:
            raise StopIteration

        # create an array of all background
        X = self.sample_from_background(independent=True)

        # create a target tensor, marking all
        # the glitch data as 0.
        y = torch.zeros((self.batch_size,))

        # replace some of this data with glitches if
        # we have glitch data to use
        if self.glitches is not None:
            # break up the number of glitches randomly
            # between hanford and livingston
            num_hanford = np.random.randint(self.num_glitches)
            num_livingston = self.num_glitches - num_hanford

            # replace the hanford channel of the
            # existing background data with some
            # sampled hanford glitches
            hanford_glitches = self.sample_from_array(
                self.hanford_glitches, num_hanford
            )
            X[:num_hanford, 0] = torch.stack(hanford_glitches)

            # replace the livingston channel of the existing
            # background data with some sampled livingston
            # glitches
            livingston_glitches = self.sample_from_array(
                self.livingston_glitches, num_livingston
            )
            X[num_hanford : self.num_glitches, 1] = torch.stack(
                livingston_glitches
            )

        # inject waveforms into the background if we have
        # generated waveforms to sample from
        if self.waveforms is not None:
            waveforms = self.sample_from_array(
                self.waveforms, self.num_waveforms
            )
            self.inject_waveforms(X[-self.num_waveforms :], waveforms)
            y[-self.num_waveforms :] = 1

        X = self.whiten(X)
        return X, y
