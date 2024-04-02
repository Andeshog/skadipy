#!/usr/bin/env python3

import pandas as pd
import numpy as np
import scipy
import scipy.io
import skadipy as mc
from typing import List

import skadipy.actuator
import skadipy.actuator._base


def save_mat(
        filename: str,
        inputs: np.ndarray,
        xi: np.ndarray,
        outputs: np.ndarray,
        thetas: np.ndarray,
        rho: np.ndarray,
        mu: np.ndarray,
        gamma: np.ndarray,
        lambda_p: np.ndarray,
        thruster: skadipy.actuator._base.ActuatorBase,
    ):

    scipy.io.savemat(
        file_name=filename,
        mdict={
            "inputs": inputs,
            "xi": xi,
            "outputs": outputs,
            "theta": thetas,
            "rho": rho,
            "mu": mu,
            "gamma": gamma,
            "lambda_p": lambda_p,
            "attributes": thruster.extra_attributes
        }
    )