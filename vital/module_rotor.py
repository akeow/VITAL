"""
module_rotor.py

Tools for working with rotor performance data, including the `RotorData` class and utility functions.

Functions:
    get_cp(tsr): Computes Cp (power coefficient) from interpolated Cq.
    get_ct(tsr): Interpolates Ct (thrust coefficient) for a given TSR.
    get_cq(tsr): Interpolates Cq (torque coefficient) for a given TSR.
    get_cpmin(tsr): Interpolates Cpmin (minimum pressure coefficient) for a given TSR.

Classes:
    RotorData: A class for managing and processing rotor performance data.

Raises:
    ValueError: If the rotor performance data file or Cpmin data file is invalid or cannot be loaded.
"""

import numpy as np
import pandas as pd
import json
from scipy.interpolate import PchipInterpolator


class RotorData:
    """
    A class for managing and processing rotor performance data.
    """

    def __init__(self, filename: str, cpmin_filename: str = None):
        """
        Initializes the RotorData object.

        Args:
            filename (str): Path to rotor performance data file.
            cpmin_filename (str, optional): Path to Cpmin data file.

        Required columns in rotor file:
            TSR, Ct, Cq
        """
        self.filename = filename
        self.cpmin_filename = cpmin_filename
        self.data = self.load_data()

        # Sort and remove duplicate TSR values
        self.data = (
            self.data.sort_values("TSR")
            .drop_duplicates(subset="TSR")
            .reset_index(drop=True)
        )

        # Required columns
        required_cols = {"TSR", "Ct", "Cq"}
        missing = required_cols - set(self.data.columns)
        if missing:
            raise ValueError(f"Rotor data file is missing required columns: {missing}")

        self.tsr = self.data["TSR"].to_numpy(dtype=float)
        self.ct = self.data["Ct"].to_numpy(dtype=float)
        self.cq = self.data["Cq"].to_numpy(dtype=float)

        # Compute Cp from Cq
        self.cp = self.tsr * self.cq

        # Load Cpmin curve
        self.cpmin = self.load_cpmin_data()

        self.prepare_data()

        # Interpolators
        self._cq_interp = PchipInterpolator(self.tsr, self.cq, extrapolate=False)
        self._ct_interp = PchipInterpolator(self.tsr, self.ct, extrapolate=False)

        self.CpOpt, self.TSROpt = self.find_max_cp()
        self.TSRmax = self.find_tsr_max()

    def load_data(self) -> pd.DataFrame:
        """
        Loads rotor performance data from a text file.
        """
        return pd.read_csv(self.filename, sep=r"\s+|\t", engine="python")

    def load_cpmin_data(self) -> np.ndarray:
        """
        Loads Cpmin data from a JSON file if provided, otherwise uses -1 everywhere.
        Uses the tip curve (index 0) from the Cpmin dataset.
        """
        if self.cpmin_filename:
            with open(self.cpmin_filename, "r") as f:
                cpmin_data = json.load(f)

            cpmin_tsr = np.array(cpmin_data["TSR"], dtype=float)
            cpmin_tip = np.array(cpmin_data["Cpmin"]["0"], dtype=float)

            return np.interp(self.tsr, cpmin_tsr, cpmin_tip)

        return -1.0 * np.ones_like(self.tsr)

    def prepare_data(self):
        """
        Applies physical sign constraints.
        """
        self.cq = np.maximum(self.cq, 0.0)
        self.ct = np.maximum(self.ct, 0.0)
        self.cpmin = np.minimum(self.cpmin, 0.0)
        self.cp = np.maximum(self.cp, 0.0)

    def _evaluate_curve(self, tsr, interpolator, values, decay_mode="curve"):
        """
        Interpolate inside the measured TSR range and apply simplified behavior
        outside the measured range.

        Behavior:
            - Inside the measured TSR range:
                Uses the supplied interpolator.

            - Below the measured TSR range:
                Holds the first measured value. This avoids forcing Cq or Ct to
                zero at TSR = 0, which can be incorrect for drag-based turbines.

            - Above the measured TSR range:
                Applies exponential decay toward zero.

        Notes:
            The extrapolated values should not be interpreted as validated rotor
            performance. Users should provide rotor data over the expected operating
            TSR range whenever possible.
        """
        scalar_input = np.isscalar(tsr)
        tsr_arr = np.atleast_1d(np.asarray(tsr, dtype=float))
        y = np.zeros_like(tsr_arr)

        tsr_min = self.tsr[0]
        tsr_max = self.tsr[-1]

        mask_in = (tsr_arr >= tsr_min) & (tsr_arr <= tsr_max)
        mask_left = tsr_arr < tsr_min
        mask_right = tsr_arr > tsr_max

        if np.any(mask_in):
            y[mask_in] = interpolator(tsr_arr[mask_in])

        # Below range: hold the first measured value.
        # Do not force Cq or Ct to zero at TSR = 0, because drag-based turbines
        # can have nonzero or maximum torque/thrust coefficients at low TSR.
        if np.any(mask_left):
            y[mask_left] = values[0]

        # Above range: exponential decay to zero.
        if np.any(mask_right):
            decay_scale = max(tsr_max, 1e-6)
            y_right = values[-1] * np.exp(
                -(tsr_arr[mask_right] - tsr_max) / decay_scale
            )
            y[mask_right] = np.maximum(0.0, y_right)

        return y[0] if scalar_input else y

    def get_cq(self, tsr):
        """
        Interpolate Cq.
        """
        return self._evaluate_curve(tsr, self._cq_interp, self.cq)

    def get_cp(self, tsr):
        """
        Compute Cp from interpolated Cq:

            Cp = TSR * Cq

        Notes:
            Even if Cq is held nonzero below the measured TSR range, Cp will still
            go to zero as TSR approaches zero because Cp is computed as TSR times Cq.
        """
        tsr_scalar = np.isscalar(tsr)
        tsr_arr = np.atleast_1d(np.asarray(tsr, dtype=float))
        cq_vals = self.get_cq(tsr_arr)
        cp_vals = tsr_arr * cq_vals
        return cp_vals[0] if tsr_scalar else cp_vals

    def get_ct(self, tsr):
        """
        Interpolate Ct.
        """
        return self._evaluate_curve(tsr, self._ct_interp, self.ct)

    def get_cpmin(self, tsr):
        """
        Interpolate Cpmin.
        """
        tsr_scalar = np.isscalar(tsr)
        tsr_arr = np.atleast_1d(np.asarray(tsr, dtype=float))

        cpmin_interp = np.interp(
            tsr_arr,
            self.tsr,
            self.cpmin,
            left=self.cpmin[0],
            right=self.cpmin[-1],
        )

        return cpmin_interp[0] if tsr_scalar else cpmin_interp

    def find_max_cp(self) -> tuple:
        """
        Find maximum Cp based on derived Cp = TSR * Cq.
        """
        cp_values = self.cp
        idx = np.argmax(cp_values)
        return cp_values[idx], self.tsr[idx]

    def find_tsr_max(self) -> float:
        """
        Find max TSR where Cp or Ct becomes zero.
        """
        tsr_values = np.linspace(self.tsr[0], self.tsr[-1] + 10, 1000)
        cp_values = self.get_cp(tsr_values)
        ct_values = self.get_ct(tsr_values)

        zero_indices = np.where((cp_values <= 0) | (ct_values <= 0))[0]
        return tsr_values[zero_indices[0]] if len(zero_indices) > 0 else tsr_values[-1]