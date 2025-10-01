"""
module_lcoe.py

This module provides tools for calculating the Levelized Cost of Energy (LCOE) for tidal turbines integrated with vessels or floating platforms.

Key Features:
-------------
- Manage and validate input data for LCOE calculations.
- Perform LCOE calculations based on CAPEX, OPEX, and annual energy production.
- Support multiple customer configurations and applications (e.g., battery charging, grid connection).
- Provide detailed breakdowns of CAPEX, OPEX, and annual energy generation.

Classes:
--------
- LCOEData: Manages and validates input data for LCOE calculations.
- LCOECalculator: Performs LCOE calculations and provides detailed breakdowns of costs and energy production.
"""

import numpy as np
import scipy as sp
from vital.constGlobal import ConstantsGlobal
from vital.constUnitConvert import ConstantsUnitConversion
from vital.module_cost_config import COST_FUNCTIONS
from vital.module_cost_calculations import operating_cost_SITKANA

# Initialize global constants from modules
GLOBAL = ConstantsGlobal()
CONVERT = ConstantsUnitConversion()


class LCOEData:
    """
    A class for managing and validating input data for LCOE calculations.

    Attributes:
        turbine_radius (float): Radius of the turbine in meters.
        turbine_rated_power (float): Rated power of the turbine in watts.
        number_of_turbines (int): Number of turbines in the system.
        hub_depth (float): Depth of the turbine hub in meters.
        dCable (float): Length of the electrical cable in meters.
        dMoor (float): Mooring depth in meters.
        Fdrag (float): Drag force acting on the vessel in newtons.
        VesselVolume (float): Volume of the vessel in cubic meters.
        Ft (np.ndarray): Thrust forces acting on the turbine over time.
        Battery (float): Battery capacity in kWh (optional).
        lifetime (int): Turbine lifetime in years.
        discount_rate (float): Discount rate for LCOE calculations.
        turbulence_intensity (float): Turbulence intensity factor.
        customer (str): Customer configuration identifier.
        application (str): Application type (e.g., battery charging, grid connection).
        power_data (np.ndarray): Electrical power data over time.
        time_data (np.ndarray): Time steps corresponding to power data.

    Methods:
        update_turbine_config(turbineConfig): Updates turbine configuration attributes.
        update_simulation_results(simResult): Updates simulation results attributes.
    """

    def __init__(self, tidalData, turbineConfig, vesselData, simResult,
                 lifetime, discount_rate, turbulence_intensity, customer, application, BatteryCapacity_kWh=None):
        """
        Initializes the LCOEData object and validates input data.

        Args:
            tidalData (object): Tidal data object containing attributes like cable length and mooring distance.
            turbineConfig (dict): Turbine configuration dictionary containing properties like radius, rated power, etc.
            vesselData (object): Vessel data object containing attributes like drag force and volume.
            simResult (dict): Simulation results dictionary containing power and time data.
            lifetime (int): Turbine lifetime in years.
            discount_rate (float): Discount rate for LCOE calculations.
            turbulence_intensity (float): Turbulence intensity factor.
            customer (str): Customer configuration identifier.
            application (str): Application type (e.g., battery charging, grid connection).
            BatteryCapacity_kWh (float, optional): Battery capacity in kWh.
        """
        # Validate turbineConfig dictionary
        required_turbine_keys = ['Radius', 'Prated', 'number_of_turbines', 'dHub']
        for key in required_turbine_keys:
            if key not in turbineConfig:
                raise ValueError(f"Missing key '{key}' in turbineConfig dictionary.")

        # Validate simResult dictionary
        required_sim_keys = ['Pelec', 't']
        for key in required_sim_keys:
            if key not in simResult:
                raise ValueError(f"Missing key '{key}' in simResult dictionary.")

        # Validate COST_FUNCTIONS (assumes it's defined globally)
        if 'COST_FUNCTIONS' not in globals():
            raise NameError("COST_FUNCTIONS is not defined. Ensure it is globally available.")

        if customer not in COST_FUNCTIONS:
            raise ValueError(f"Customer '{customer}' not found in COST_FUNCTIONS.")
        if application not in COST_FUNCTIONS[customer]['applications']:
            raise ValueError(f"Application '{application}' not found for customer '{customer}' in COST_FUNCTIONS.")

        # Initialize attributes
        self.turbine_radius = turbineConfig['Radius']
        self.turbine_rated_power = turbineConfig['Prated']
        self.number_of_turbines = turbineConfig['number_of_turbines']
        self.hub_depth = turbineConfig['dHub']
        self.dCable = tidalData.cable_length
        self.dMoor = tidalData.mooring_distance
        self.Fdrag = vesselData.Fdrag
        self.VesselVolume = vesselData.VesselVolume
        self.Ft = simResult['Ft']
        self.Battery = BatteryCapacity_kWh

        self.lifetime = lifetime
        self.discount_rate = discount_rate
        self.turbulence_intensity = turbulence_intensity
        self.customer = customer
        self.application = application

        # Store simulation results
        self.power_data = simResult['Pelec']
        self.time_data = simResult['t']

    def update_turbine_config(self, turbineConfig):
        """
        Updates turbine configuration attributes.

        Args:
            turbineConfig (dict): Turbine configuration dictionary containing updated properties.
        """
        required_turbine_keys = ['Radius', 'Prated', 'number_of_turbines', 'dHub']
        for key in required_turbine_keys:
            if key not in turbineConfig:
                raise ValueError(f"Missing key '{key}' in turbineConfig dictionary.")
        self.turbine_radius = turbineConfig['Radius']
        self.turbine_rated_power = turbineConfig['Prated']
        self.number_of_turbines = turbineConfig['number_of_turbines']
        self.hub_depth = turbineConfig['dHub']

    def update_simulation_results(self, simResult):
        """
        Updates simulation results attributes.

        Args:
            simResult (dict): Simulation results dictionary containing updated power and time data.
        """
        required_sim_keys = ['Pelec', 't']
        for key in required_sim_keys:
            if key not in simResult:
                raise ValueError(f"Missing key '{key}' in simResult dictionary.")
        self.power_data = simResult['Pelec']
        self.time_data = simResult['t']


class LCOECalculator:
    """
    A class for performing Levelized Cost of Energy (LCOE) calculations.

    Attributes:
        data (LCOEData): LCOEData object containing input data for calculations.
        capex (dict): Dictionary to store CAPEX components.
        opex (dict): Dictionary to store OPEX components.
        instantaneous_power (np.ndarray): Instantaneous power data over time.
        time_series (np.ndarray): Time steps corresponding to instantaneous power data.

    Methods:
        set_instantaneous_power(): Calculates instantaneous power and stores time series.
        calculate_annual_energy(): Calculates annual energy production in kWh.
        calculate_capacity_factor(): Calculates capacity factor based on annual energy and rated power.
        calculate_total_capex(): Calculates total CAPEX based on customer configuration and application type.
        calculate_total_opex(total_capex): Calculates total OPEX based on CAPEX and customer configuration.
        calculate_lcoe(): Calculates the Levelized Cost of Energy (LCOE).
        list_capex(): Lists all CAPEX components and their values.
        list_opex(total_capex): Lists all OPEX components and their values.
        list_annual_energy(): Lists annual energy generation.
    """

    def __init__(self, lcoe_data):
        """
        Initializes the LCOECalculator object.

        Args:
            lcoe_data (LCOEData): LCOEData object containing input data for calculations.
        """
        self.data = lcoe_data
        self.capex = {}
        self.opex = {}
        self.instantaneous_power = None
        self.time_series = None

    def set_instantaneous_power(self):
        """
        Calculates instantaneous power and stores time series.

        Raises:
            TypeError: If `power_data` or `time_data` is not a list or numpy array.
            ValueError: If `power_data` and `time_data` lengths do not match.
        """
        if not isinstance(self.data.power_data, (list, np.ndarray)):
            raise TypeError("power_data must be a list or numpy array.")
        if not isinstance(self.data.time_data, (list, np.ndarray)):
            raise TypeError("time_data must be a list or numpy array.")
        if len(self.data.power_data) != len(self.data.time_data):
            raise ValueError("power_data and time_data must have the same length.")

        self.instantaneous_power = np.array(self.data.power_data) / ((1 + self.data.turbulence_intensity) ** 3) * self.data.number_of_turbines
        self.time_series = np.array(self.data.time_data)

    def calculate_annual_energy(self):
        """
        Calculates annual energy production in kWh.

        Returns:
            float: Annual energy production in kWh.
        """
        if self.instantaneous_power is None or self.time_series is None:
            self.set_instantaneous_power()
        
        dt = np.mean(np.diff(self.time_series))
        total_energy_generated = sp.integrate.simpson(self.instantaneous_power, dx=dt)  # Total energy in Joules
        average_power = total_energy_generated / (self.time_series[-1] - self.time_series[0])  # Average power in watts
        annual_energy = average_power * 8760 / 1000  # Convert to annual energy (kWh); 365*24 = 8760
        return annual_energy

    def calculate_capacity_factor(self):
        """
        Calculates capacity factor based on annual energy and rated power.

        Returns:
            float: Capacity factor (ratio of actual energy to maximum possible energy).
        """
        annual_energy = self.calculate_annual_energy()
        max_annual_energy = self.data.turbine_rated_power * 8760 / 1000  # Maximum annual energy in kWh; 365*24 = 8760
        capacity_factor = annual_energy / max_annual_energy
        return capacity_factor

    def calculate_total_capex(self):
        """
        Calculates total CAPEX based on customer configuration and application type.

        Returns:
            float: Total CAPEX in USD.

        Raises:
            ValueError: If battery capacity is invalid for non-grid_connection applications.
        """
        if self.data.application == 'grid_connection':
            self.data.Battery = 0
        elif self.data.Battery is None or self.data.Battery <= 0:
            raise ValueError("Battery capacity must be greater than zero for non-grid_connection applications.")

        common_params = {
            'turbine_radius_m': self.data.turbine_radius,
            'turbine_rated_power_W': self.data.turbine_rated_power,
            'number_of_turbines': self.data.number_of_turbines,
            'electrical_cable_length_m': self.data.dCable,
            'mooring_cable_length_m': self.data.dMoor,
            'force_vessel_drag_N': self.data.Fdrag,
            'force_turbine_thrust_N': self.data.Ft,
            'vessel_volume_m3': self.data.VesselVolume,
            'BatteryCapacity_kWh': self.data.Battery,
        }

        for cost_name, cost_function in COST_FUNCTIONS[self.data.customer]['rotor_and_drivetrain'].items():
            self.capex[cost_name] = cost_function(**common_params)

        for cost_name, cost_function in COST_FUNCTIONS[self.data.customer]['applications'][self.data.application].items():
            self.capex[cost_name] = cost_function(**common_params)

        total_capex_usd = sum(self.capex.values())
        
        if self.data.customer == 'customer_A':  # HDPS
            total_capex_usd *= (1 + 0.05)
        
        return total_capex_usd

    def calculate_total_opex(self, total_capex):
        """
        Calculates total OPEX based on CAPEX and customer configuration.

        Args:
            total_capex (float): Total CAPEX in USD.

        Returns:
            float: Total OPEX in USD.
        """
        if self.data.customer == 'customer_B':  # SITKANA
            total_opex_usd = operating_cost_SITKANA(self.data.turbine_rated_power, self.data.number_of_turbines)
        else:
            total_opex_usd = 0.04 * total_capex

        return total_opex_usd

    def calculate_lcoe(self):
        """
        Calculates the Levelized Cost of Energy (LCOE).

        Returns:
            float: LCOE in USD/kWh.

        Raises:
            ValueError: If present value of energy is zero.
        """
        total_capex = self.calculate_total_capex()
        total_opex = self.calculate_total_opex(total_capex)
        annual_energy = self.calculate_annual_energy()

        pvc = total_capex + total_opex * np.sum([1 / (1 + self.data.discount_rate)**t for t in range(1, self.data.lifetime + 1)])
        pve = annual_energy * np.sum([1 / (1 + self.data.discount_rate)**t for t in range(1, self.data.lifetime + 1)])

        if pve == 0:
            raise ValueError("Present value of energy is zero, cannot calculate LCOE.")
        
        lcoe = pvc / pve
        return lcoe

    def list_capex(self):
        """
        Lists all CAPEX components and their values.

        Raises:
            ValueError: If CAPEX has not been calculated yet.
        """
        if not self.capex:
            raise ValueError("CAPEX has not been calculated yet. Please calculate CAPEX first.")
        
        print("CAPEX Components:")
        for cost_name, cost_value in self.capex.items():
            print(f"  {cost_name}: ${cost_value:.2f}")
        print(f"Total CAPEX: ${sum(self.capex.values()):.2f}")

    def list_opex(self, total_capex):
        """
        Lists all OPEX components and their values.

        Args:
            total_capex (float): Total CAPEX in USD.
        """
        total_opex = self.calculate_total_opex(total_capex)
        print("OPEX Components:")
        if self.data.customer == 'customer_B':  # SITKANA
            print(f"  SITKANA Operating Cost: ${total_opex:.2f}")
        else:
            print(f"  Standard Operating Cost (4% of CAPEX): ${total_opex:.2f}")
        print(f"Total OPEX: ${total_opex:.2f}")

    def list_annual_energy(self):
        """
        Lists the annual energy generation.
        """
        annual_energy = self.calculate_annual_energy()
        print(f"Annual Energy Generation: {annual_energy:.2f} kWh")