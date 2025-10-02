"""
module_constraint_checker.py

This module provides tools for checking various constraints for turbine and vessel configurations, including power, depth, cavitation, and pitch stability.

Key Features:
    * Validate turbine and vessel performance against power constraints.
    * Ensure rotor depth is sufficient for submersion.
    * Check cavitation constraints based on pressure coefficients and flow speeds.
    * Verify pitch stability constraints for vessel operation.
"""

import numpy as np
from vital.constGlobal import ConstantsGlobal
import matplotlib.pyplot as plt

plt.style.use('tableau-colorblind10')


class ConstraintChecker:
    """
    A class for checking various constraints for turbine and vessel configurations.
    """
    # Attributes:
    #     Radius (float): Rotor radius in meters.
    #     dHub (float): Hub depth in meters.
    #     Prated (float): Rated power in watts.
    #     number_of_turbines (int): Number of turbines in the system.
    #     CpminFunc (function): Function to calculate Cpmin (minimum pressure coefficient) based on TSR.
    #     GLOBAL (ConstantsGlobal): Global constants for physical properties.
    #     TSR (np.ndarray): Tip-speed ratio over time from simulation results.
    #     Uinf_adjusted (np.ndarray): Adjusted flow speeds over time from simulation results.
    #     Pelec (np.ndarray): Electrical power over time from simulation results.
    #     Ft (np.ndarray): Thrust forces over time from simulation results.
    #     wr (np.ndarray): Rotor angular velocity over time from simulation results.
    #     Kphi (float): Vessel pitch hydrostatic stiffness.
    #     phi (float): Vessel pitch angle in radians.
    #     theta_m (float): Mooring line angle in radians.
    #     area (float): Cross-sectional area of the vessel.
    #     Xm (float): Horizontal distance from the center of rotation.
    #     Zm (float): Vertical distance from the center of rotation.

    # Methods:
    #     power_constraint(): Calculates power constraint values.
    #     check_power_constraint(): Checks if the power constraint is satisfied.
    #     depth_constraint(): Calculates depth constraint values.
    #     check_depth_constraint(): Checks if the depth constraint is satisfied.
    #     cavitation_constraint(): Calculates cavitation constraint values.
    #     check_cavitation_constraint(): Checks if the cavitation constraint is satisfied.
    #     pitch_constraint(): Calculates pitch constraint values.
    #     check_pitch_constraint(): Checks if the pitch constraint is satisfied.


    def __init__(self, rotorData, turbineConfig, vesselConfig, simResult):
        """
        Initializes the ConstraintChecker object.

        Args:
            rotorData (object): Rotor data object containing methods like `get_cpmin`.
            turbineConfig (dict): Turbine configuration dictionary containing properties like radius, hub depth, etc.
            vesselConfig (object): Vessel configuration object containing vessel properties like pitch stiffness and geometry.
            simResult (dict): Simulation results containing flow speeds, thrust forces, tip-speed ratio, etc.
        """
        self.Radius = turbineConfig['Radius']
        self.dHub = turbineConfig['dHub']
        self.Prated = turbineConfig['Prated']
        self.number_of_turbines = turbineConfig['number_of_turbines']
        self.CpminFunc = rotorData.get_cpmin

        # Global constants
        self.GLOBAL = ConstantsGlobal()
        self.rho = self.GLOBAL.rho
        self.g = self.GLOBAL.g
        self.Pvap = self.GLOBAL.Pvap
        self.Patm = self.GLOBAL.Patm

        # Simulation results
        self.TSR = simResult['TSR']
        self.Uinf_adjusted = simResult['Uinf_adjusted']
        self.Pelec = simResult['Pelec']
        self.Ft = simResult['Ft']
        self.wr = simResult['wr']

        # Vessel configuration
        self.Kphi = vesselConfig.Kphi
        self.phi = vesselConfig.phi
        self.theta_m = vesselConfig.theta_m
        self.area = vesselConfig.area
        self.Xm = vesselConfig.Xm
        self.Zm = vesselConfig.Zm

    def power_constraint(self):
        """
        Calculates power constraint values.

        Returns:
            np.ndarray: Power constraint values (must be <= 0 to be valid).
        """
        return self.Prated - self.Pelec

    def check_power_constraint(self):
        """
        Checks if the power constraint is satisfied.

        Returns:
            bool: True if satisfied (Pelec > 0 and Pelec <= Prated), False otherwise.
        """
        return np.all(self.Pelec > 0) and np.all(self.power_constraint() >= 0)

    def depth_constraint(self):
        """
        Calculates depth constraint values.

        Returns:
            np.ndarray: Depth constraint values (must be > 0 to be valid, rotor must be submerged).
        """
        return self.dHub - self.Radius

    def check_depth_constraint(self):
        """
        Checks if the depth constraint is satisfied.

        Returns:
            bool: True if satisfied, False otherwise.
        """
        return np.all(self.depth_constraint() > 0)

    def cavitation_constraint(self):
        """
        Calculates cavitation constraint values.

        Returns:
            np.ndarray: Cavitation constraint values (must be > 0 to be valid).
        """
        Vinf = np.sqrt(self.Uinf_adjusted**2 + (self.Radius * self.wr)**2)
        Pinf = self.Patm + self.rho * self.g * (self.dHub - self.Radius)  # Pressure at rotor tip
        Cpmin = self.CpminFunc(self.TSR)  # Pressure coefficient for cavitation
        return 0.5 * self.rho * Vinf**2 * Cpmin - (self.Pvap - Pinf)

    def check_cavitation_constraint(self):
        """
        Checks if the cavitation constraint is satisfied.

        Returns:
            bool: True if satisfied, False otherwise.
        """
        return np.all(self.cavitation_constraint() > 0)

    def pitch_constraint(self):
        """
        Calculates pitch constraint values.

        Returns:
            np.ndarray: Pitch constraint values (must be > 0 to be valid).
        """
        F_vessel_thrust = 0.5 * self.rho * self.area * self.Uinf_adjusted**2
        F_turbine_thrust = self.number_of_turbines * self.Ft
        F_total = F_vessel_thrust + F_turbine_thrust

        return (
            self.Kphi * self.phi -
            F_turbine_thrust * self.dHub -
            F_total * self.Xm * np.cos(self.theta_m) -
            F_total * self.Zm * np.sin(self.theta_m)
        )

    def check_pitch_constraint(self):
        """
        Checks if the pitch constraint is satisfied.

        Returns:
            bool: True if satisfied, False otherwise.
        """
        return np.all(self.pitch_constraint() > 0)