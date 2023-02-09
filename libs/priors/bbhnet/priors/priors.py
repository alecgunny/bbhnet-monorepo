import numpy as np
from bilby.core.prior import (
    Constraint,
    Cosine,
    Gaussian,
    LogNormal,
    PowerLaw,
    Sine,
    Uniform,
)
from bilby.gw.prior import (
    BBHPriorDict,
    UniformComovingVolume,
    UniformSourceFrame,
)

from bbhnet.priors.utils import read_priors_from_file

# Unit names
msun = r"$M_{\odot}$"
mpc = "Mpc"
rad = "rad"


def uniform_extrinsic() -> BBHPriorDict:
    prior = BBHPriorDict()
    prior["dec"] = Cosine()
    prior["ra"] = Uniform(0, 2 * np.pi)
    prior["theta_jn"] = 0
    prior["phase"] = 0

    return prior


def nonspin_bbh() -> BBHPriorDict:
    prior = uniform_extrinsic()
    prior["mass_1"] = Uniform(5, 100, unit=msun)
    prior["mass_2"] = Uniform(5, 100, unit=msun)
    prior["mass_ratio"] = Constraint(0, 1)
    prior["redshift"] = UniformSourceFrame(0, 0.5, unit=mpc, name="redshift")
    prior["psi"] = 0
    prior["a_1"] = 0
    prior["a_2"] = 0
    prior["tilt_1"] = 0
    prior["tilt_2"] = 0
    prior["phi_12"] = 0
    prior["phi_jl"] = 0

    return prior


def end_o3_ratesandpops() -> BBHPriorDict:
    prior = uniform_extrinsic()
    prior["mass_1"] = PowerLaw(alpha=-2.35, minimum=2, maximum=100, unit=msun)
    prior["mass_2"] = PowerLaw(alpha=1, minimum=2, maximum=100, unit=msun)
    prior["mass_ratio"] = Constraint(0.02, 1)
    prior["redshift"] = UniformComovingVolume(0, 2, unit=mpc, name="redshift")
    prior["psi"] = 0
    prior["a_1"] = Uniform(0, 0.998)
    prior["a_2"] = Uniform(0, 0.998)
    prior["tilt_1"] = Sine(unit=rad)
    prior["tilt_2"] = Sine(unit=rad)
    prior["phi_12"] = Uniform(0, 2 * np.pi)
    prior["phi_jl"] = 0

    return prior


def power_law_dip_break():
    prior = uniform_extrinsic()
    event_file = "./event_files/\
        O1O2O3all_mass_h_iid_mag_iid_tilt_powerlaw_redshift_maxP_events_bbh.h5"
    prior |= read_priors_from_file(event_file)

    return prior


def gaussian_masses(m1: float, m2: float, sigma: float = 2):
    """
    Constructs a gaussian bilby prior for masses.
    Args:
        m1: mean of the Gaussian distribution for mass 1
        m2: mean of the Gaussian distribution for mass 2
        sigma: standard deviation of the Gaussian distribution for both masses

    Returns a BBHpriorDict
    """
    prior_dict = BBHPriorDict()
    prior_dict["mass_1"] = Gaussian(name="mass_1", mu=m1, sigma=sigma)
    prior_dict["mass_2"] = Gaussian(name="mass_2", mu=m2, sigma=sigma)
    prior_dict["luminosity_distance"] = UniformSourceFrame(
        name="luminosity_distance", minimum=100, maximum=3000, unit="Mpc"
    )
    prior_dict["dec"] = Cosine(name="dec")
    prior_dict["ra"] = Uniform(
        name="ra", minimum=0, maximum=2 * np.pi, boundary="periodic"
    )

    return prior_dict


def log_normal_masses(m1: float, m2: float, sigma: float = 2):
    """
    Constructs a log normal bilby prior for masses.
    Args:
        m1: mean of the Log Normal distribution for mass 1
        m2: mean of the Log Normal distribution for mass 2
        sigma: standard deviation for m1 and m2

    Returns a BBHpriorDict
    """
    prior_dict = BBHPriorDict()
    prior_dict["mass_1"] = LogNormal(name="mass_1", mu=m1, sigma=sigma)
    prior_dict["mass_2"] = LogNormal(name="mass_2", mu=m2, sigma=sigma)
    prior_dict["luminosity_distance"] = UniformSourceFrame(
        name="luminosity_distance", minimum=100, maximum=3000, unit="Mpc"
    )
    prior_dict["dec"] = Cosine(name="dec")
    prior_dict["ra"] = Uniform(
        name="ra", minimum=0, maximum=2 * np.pi, boundary="periodic"
    )

    return prior_dict
