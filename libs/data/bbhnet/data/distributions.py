import math
from typing import Optional

import torch


class Uniform:
    def __init__(self, low: float = 0, high: float = 1) -> None:
        self.low = low
        self.high = high

    def __call__(self, N: int) -> torch.Tensor:
        return self.low + torch.rand(size=(N,)) * (self.high - self.low)


class Cosine:
    def __init__(
        self, low: float = -math.pi / 2, high: float = math.pi / 2
    ) -> None:
        self.low = low
        self.norm = 1 / (math.sin(high) - math.sin(low))

    def __call__(self, N: int) -> torch.Tensor:
        """
        Implementation lifted from
        https://lscsoft.docs.ligo.org/bilby/_modules/bilby/core/prior/analytical.html#Cosine # noqa
        """
        u = torch.rand(size=(N,))
        return torch.arcsin(u / self.norm + math.sin(self.low))


class LogNormal:
    def __init__(
        self, mean: float, std: float, low: Optional[float] = None
    ) -> None:
        self.sigma = math.log((std / mean) ** 2 + 1) ** 0.5
        self.mu = 2 * math.log(mean / (mean**2 + std**2) ** 0.25)
        self.low = low

    def __call__(self, N: int) -> torch.Tensor:
        u = self.mu + torch.randn(N) * self.sigma
        x = torch.exp(u)
        if self.low is not None:
            x = torch.clip(x, self.low)
        return x