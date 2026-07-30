"""
module_vessel.py

This module provides tools for managing vessel properties and calculating forces such as drag and mooring forces.

Key Features:
-------------
* Represent vessel geometry and physical properties.
* Support user-defined vessel configurations or default properties.
* Calculate drag forces exerted on the vessel based on flow speeds.
* Provide utility methods for printing attributes and managing vessel properties.

Classes:
--------
* VesselData: Represents vessel properties and provides methods for force calculations.
"""

import numpy as np
from vital.constGlobal import ConstantsGlobal

# Initialize global constants
GLOBAL = ConstantsGlobal()


class VesselData:
    """
    A class to represent the data and properties of a vessel.
    """
    # Attributes:
    #     height (float): Height of the vessel in meters.
    #     density (float): Density of the vessel material in kg/m^3.
    #     theta_m (float): Mooring line angle in radians.
    #     alpha (float): Aspect ratio for the vessel.
    #     Cd (float): Drag coefficient.
    #     phi (float): Pitch constraint in radians.
    #     user_defined (bool): Flag indicating if the vessel properties are user-defined.
    #     vessel_properties (dict): Dictionary containing user-defined vessel properties.
    #     width (float): Width of the vessel in meters.
    #     Fmoor (float): Mooring force in Newtons.
    #     length (float): Length of the vessel in meters.
    #     Khs (float): Hydrostatic stiffness in N/m.
    #     Kphi (float): Pitch hydrostatic stiffness in N/m.
    #     GM (float): Metacentric height in meters.
    #     VesselVolume (float): Volume of the vessel in cubic meters.
    #     h_s (float): Submerged height; half of the vessel height in meters.
    #     area (float): Cross-sectional area of the vessel in square meters.
    #     Fdrag (float): Drag force exerted on the vessel in Newtons.

    # Methods:
    #     set_vessel_properties(): Sets vessel properties from user-defined geometry.
    #     set_default_properties(): Sets default properties for the vessel.
    #     calculate_vessel_drag_force(Uinf): Calculates the drag force exerted on the vessel.
    #     print_all_attributes(): Prints all attributes of the VesselData object.


    def __init__(self, height=None, density=None, theta_m=None, alpha=None, Cd=None, phi=None, user_defined=False, vessel_properties=None, simResult=None):
        """
        Constructs all the necessary attributes for the VesselData object.

        Args:
            height (float, optional): Height of the vessel in meters (default is None).
            density (float, optional): Density of the vessel material in kg/m^3 (default is None).
            theta_m (float, optional): Mooring line angle in radians (default is None). 
            alpha (float, optional): Aspect ratio for the vessel (default is None).
            Cd (float, optional): Drag coefficient (default is None).
            phi (float, optional): Pitch constraint in radians (default is None).
            user_defined (bool, optional): Flag indicating if the vessel properties are user-defined (default is False).
            vessel_properties (dict, optional): Dictionary containing user-defined vessel properties (default is None).
            simResult (dict, optional): Simulation results containing flow speed adjustments (default is None).
        """
        self.height = height
        self.density = density
        self.theta_m = theta_m
        self.alpha = alpha
        self.Cd = Cd
        self.phi = phi
        self.user_defined = user_defined
        self.vessel_properties = vessel_properties or {}

        self.width = None
        self.Fmoor = None
        self.length = None
        self.Khs = None
        self.Kphi = None
        self.GM = None
        self.VesselVolume = None
        self.h_s = None
        self.area = None
        self.Fdrag = None

        if self.user_defined and self.vessel_properties:
            self.set_vessel_properties()
        else:
            self.set_default_properties()

        # Calculate drag force if simulation results are provided
        if simResult and 'Uinf_adjusted' in simResult:
            self.Fdrag = self.calculate_vessel_drag_force(simResult['Uinf_adjusted'])

    def set_vessel_properties(self):
        """
        Sets vessel properties from user-defined vessel geometry.

        Raises:
            ValueError: If a required key is missing in `vessel_properties`.
        """
        try:
            self.Xm = self.vessel_properties['Xm']
            self.Zm = self.vessel_properties['Zm']
            self.Kphi = self.vessel_properties['Kphi']
            self.theta_m = self.vessel_properties['theta']
            self.phi = self.vessel_properties['phi']
            self.area = self.vessel_properties['area']
            self.Cd = self.vessel_properties['Cd']
        except KeyError as e:
            raise ValueError(f"Missing key in vessel_properties: {e}")

    def set_default_properties(self):
        """
        Sets default vessel properties.

        Default values are used when user-defined vessel properties are not
        supplied.

        Defaults:
            height: 0.5 m
            density: 500.0 kg/m^3
            theta_m: 45 degrees
            alpha: 4.0
            Cd: 0.25
            phi: 10 degrees

        The method also calculates the submerged height and default
        cross-sectional area.
        """
        if self.height is None:
            self.height = 0.5  # Default height
        if self.density is None:
            self.density = 500.0  # Default density (kg/m^3)
        if self.theta_m is None:
            self.theta_m = 45.0 * np.pi / 180.0  # Default mooring line angle (radians)
        if self.alpha is None:
            self.alpha = 4.0  # Default aspect ratio
        if self.Cd is None:
            self.Cd = 0.25  # Default drag coefficient
        if self.phi is None:
            self.phi = 10.0 * np.pi / 180.0  # Default pitch constraint (radians)
        self.h_s = self.height / 2
        self.area = self.height * self.alpha  # Default cross-sectional area

    def calculate_vessel_drag_force(self, Uinf):
        """
        Calculates the drag force exerted on the vessel.

        Args:
            Uinf (float): Free stream velocity (m/s).

        Returns:
            float: The drag force exerted on the vessel (N).

        Raises:
            ValueError: If vessel area is not defined.
        """
        rho = GLOBAL.rho

        if self.area is None:
            raise ValueError("Vessel area is not defined.")
        return 0.5 * rho * self.Cd * self.area * Uinf**2

    def print_all_attributes(self):
        """
        Prints all attributes of the VesselData object.

        This method iterates through all attributes of the object and prints their names and values.
        """
        for attribute, value in vars(self).items():
            print(f"{attribute}: {value}")

    # Uncomment and implement as needed
    # def calculate_mooring_force(self, Uinf, Ft):
    #     """
    #     Calculate the time-domain mooring force.
    #     
    #     Parameters
    #     ----------
    #     Uinf : array
    #         Array of flow speeds.
    #     Ft : array
    #         Array of thrust forces.
    #     
    #     Returns
    #     -------
    #     array
    #         Mooring force values.
    #     """
    #     theta_m = self.theta_m
    #     height = self.height
    #     Cd = self.Cd
    #     width = self.width

    #     Fmoor = (0.25 * Cd * height * self.rho * width * Uinf**2 + Ft) / np.sin(theta_m)
    #     return Fmoor