"""
module_rotor.py

Tools for working with rotor performance data, including the `RotorData` class and utility functions.

Functions:
    get_cp(tsr): Interpolates Cp (power coefficient) for a given TSR.
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

class RotorData:
    """
    A class for managing and processing rotor performance data.
    """

    def __init__(self, filename: str, cpmin_filename: str = None):
        """
        Initializes the RotorData object.

        Args:
            filename (str): The path to the rotor performance data file.
            cpmin_filename (str, optional): The path to the Cpmin data file.

        Attributes:
            filename (str): The path to the rotor performance data file.
            cpmin_filename (str): The path to the Cpmin data file (optional).
            data (pd.DataFrame): The DataFrame containing rotor performance data.
            tsr (np.ndarray): The tip-speed ratio values from the rotor data.
            cp (np.ndarray): The power coefficient (Cp) values from the rotor data.
            ct (np.ndarray): The thrust coefficient (Ct) values from the rotor data.
            cq (np.ndarray): The torque coefficient (Cq) values derived from Cp and TSR.
            cpmin (np.ndarray): The minimum pressure coefficient (Cpmin) values.
            CpOpt (float): The optimal Cp value.
            TSROpt (float): The optimal TSR value corresponding to CpOpt.
            TSRmax (float): The maximum TSR value where Cp or Ct becomes zero.
        """
        self.filename = filename
        self.cpmin_filename = cpmin_filename
        self.data = self.load_data()
        self.tsr = self.data['TSR'].values
        self.cp = self.data['Cp'].values
        self.ct = self.data['Ct'].values
        self.cq = self.cp / self.tsr
        self.cpmin = self.load_cpmin_data()
        self.prepare_data()
        self.CpOpt, self.TSROpt = self.find_max_cp()
        self.TSRmax = self.find_tsr_max()

    def load_data(self) -> pd.DataFrame:
        """
        Loads rotor performance data from a text file.

        Returns:
            pd.DataFrame: The DataFrame containing rotor performance data.
        """
        return pd.read_csv(self.filename, delimiter='\t')

    def load_cpmin_data(self) -> np.ndarray:
        """
        Loads Cpmin data from a JSON file if provided, otherwise sets default values.

        Returns:
            np.ndarray: The Cpmin values corresponding to TSR values.
        """
        if self.cpmin_filename:
            with open(self.cpmin_filename, 'r') as f:
                cpmin_data = json.load(f)
            return np.array(cpmin_data['Cpmin']['0'])  # Assuming spanRatio[0] corresponds to the tip of the blade
        else:
            return -1 * np.ones_like(self.tsr)

    def prepare_data(self):
        """
        Ensures Cp/Ct values are positive and Cpmin values are negative or zero.
        """
        self.cq = np.maximum(self.cq, 0)
        self.ct = np.maximum(self.ct, 0)
        self.cpmin = np.minimum(self.cpmin, 0)

    def find_max_cp(self) -> tuple:
        """
        Finds the maximum Cp value and its corresponding TSR.

        Returns:
            tuple: A tuple containing:
                CpOpt (float): The optimal Cp value.
                TSROpt (float): The optimal TSR value corresponding to CpOpt.
        """
        max_cp_index = np.argmax(self.cp)
        return self.cp[max_cp_index], self.tsr[max_cp_index]

    def get_cp(self, tsr: float) -> float:
        """
        Interpolates Cp (power coefficient) for a given TSR.

        Args:
            tsr (float): The tip-speed ratio.

        Returns:
            float: The interpolated Cp value.
        """
        return np.interp(tsr, self.tsr, self.cp)

    def get_ct(self, tsr: float) -> float:
        """
        Interpolates Ct (thrust coefficient) for a given TSR.

        Args:
            tsr (float): The tip-speed ratio.

        Returns:
            float: The interpolated Ct value.
        """
        return np.interp(tsr, self.tsr, self.ct)

    def get_cq(self, tsr: float) -> float:
        """
        Interpolates Cq (torque coefficient) for a given TSR.

        Args:
            tsr (float): The tip-speed ratio.

        Returns:
            float: The interpolated Cq value.
        """
        return np.interp(tsr, self.tsr, self.cq)

    def get_cpmin(self, tsr: float) -> float:
        """
        Interpolates Cpmin (minimum pressure coefficient) for a given TSR.

        Args:
            tsr (float): The tip-speed ratio.

        Returns:
            float: The interpolated Cpmin value.
        """
        return np.interp(tsr, self.tsr, self.cpmin)

    def find_tsr_max(self) -> float:
        """
        Finds the maximum TSR where Cp or Ct becomes zero.

        Returns:
            float: The maximum TSR value where Cp or Ct becomes zero.
        """
        tsr_values = np.linspace(self.tsr[0], self.tsr[-1] + 10, 1000)
        cp_values = self.get_cp(tsr_values)
        zero_indices = np.where(cp_values <= 0)[0]
        return tsr_values[zero_indices[0]] if len(zero_indices) > 0 else tsr_values[-1]