"""
module_rotor_simulation.py

This module provides tools for simulating rotor dynamics and calculating turbine performance metrics, including mechanical power, electrical power, torque, and thrust force.

Key Features:
- Simulate turbine dynamics under varying flow speeds and depths.
- Calculate hydro torque, thrust force, and power metrics (mechanical, electrical, fluid).
- Handle closed-loop and open-loop turbine dynamics.
- Adjust flow speed based on hub depth and mooring depth.
- Retrieve simulation results for analysis and visualization.
"""
import numpy as np
from vital.constGlobal import ConstantsGlobal
import scipy as sp
from vital.unit_weight import UnitWeight  # Import the function from the new file


class RotorSimulation:
    """
    A class for simulating rotor dynamics and calculating turbine performance metrics.

    Attributes:
        - Radius (float): Rotor radius in meters.
        - Prated (float): Rated power in watts.
        - Trated (float): Rated torque in Nm.
        - dHub (float): Hub depth in meters.
        - dMoor (float): Mooring depth in meters.
        - Uinf (np.ndarray): Flow speeds at the surface in m/s.
        - t (np.ndarray): Time steps for the simulation.
        - CpFunc (function): Function to calculate Cp (power coefficient) based on TSR.
        - CqFunc (function): Function to calculate Cq (torque coefficient) based on TSR.
        - CtFunc (function): Function to calculate Ct (thrust coefficient) based on TSR.
        - CpOpt (float): Optimal Cp value.
        - TSROpt (float): Optimal TSR value corresponding to CpOpt.
        - TSRmax (float): Maximum TSR value where Cp or Ct becomes zero.
        - Ng (float): Gear ratio.
        - J_d (float): Drivetrain inertia.
        - B_d (float): Drivetrain friction.
        - J_r (float): Rotor inertia.
        - Kt (float): Torque constant.
        - Rw (float): Generator resistance.
        - I_eff (float): Effective inertia of the system.
        - GLOBAL (ConstantsGlobal): Global constants for physical properties.

    Methods:
        - simulate(): Simulates turbine dynamics and calculates performance metrics.
        - get_results(): Retrieves simulation results for analysis.
        - flowAtDepth(): Adjusts flow speed based on hub depth and mooring depth.
        - calculate_hydro_torque(): Calculates hydro torque based on flow speed and Cq.
        - calculate_thrust_force(): Calculates thrust force based on flow speed and Ct.
        - calculate_power(): Calculates power metrics (mechanical, electrical, fluid).
    """
    def __init__(self, config):
        """
        Initializes the RotorSimulation object with user-defined and tidal data parameters.

        Args:
            config (dict): Configuration dictionary containing simulation parameters.
        """
        self.Radius = config['Radius']
        self.Prated = config['Prated']
        self.Trated = config['Trated']
        self.dHub = config['dHub']
        self.dMoor = config['dMoor']
        self.Uinf = config['Uinf']
        self.t = config['t']
        self.CpFunc = config['CpFunc']
        self.CqFunc = config['CqFunc']
        self.CtFunc = config['CtFunc']
        self.CpOpt = config['CpOpt']
        self.TSROpt = config['TSROpt']
        self.TSRmax = config['TSRmax']

        self.Ng = config['Ng']
        self.J_d = config['J_d']
        self.B_d = config['B_d']
        self.J_r = config['J_r']
        self.Kt = config['Kt']
        self.Rw = config['Rw']
        self.I_eff = self.J_r / self.Ng**2 + self.J_d  # Effective inertia

        self.GLOBAL = ConstantsGlobal()
        self.Kopt = self.calculate_Kopt()

        self.initialize_results()
        self.dHub_array = np.ones(np.shape(self.t)) * self.dHub
        self.Uinf_adjusted = self.flowAtDepth(self.Uinf, self.Radius, self.dHub_array, self.dMoor)

    def initialize_results(self):
        """
        Initializes arrays to store simulation results.
        """
        self.w = np.zeros(np.shape(self.t))
        self.wr = np.zeros(np.shape(self.t))
        self.wd = np.zeros(np.shape(self.t))
        self.TSR = np.zeros(np.shape(self.t))
        self.Tg = np.zeros(np.shape(self.t))
        self.Th = np.zeros(np.shape(self.t)) 
        self.Ft = np.zeros(np.shape(self.t))
        self.Uinf_adjusted = np.zeros(np.shape(self.t))
        self.dHub_array = np.zeros(np.shape(self.t)) 

    def turbine_dynamics_closeloop(self, t, w):  # Define the ODE system
        U = np.interp(t, self.t, self.Uinf_adjusted)
        wr = w / self.Ng
        lambda_ = wr * self.Radius / U
        tau_hydro = self.calculate_hydro_torque(self.Radius, U, self.CqFunc(lambda_))
        tau_g = self.Kopt * (wr)**2 / self.Ng
        dw_dt = (tau_hydro / self.Ng - tau_g - self.B_d * w) / self.I_eff
        return dw_dt

    def turbine_dynamics_openloop(self, t, w):  # Define the ODE system
        U = np.interp(t, self.t, self.Uinf_adjusted)
        tau_g = np.interp(t, self.t, self.Tg)
        wr = w / self.Ng
        lambda_ = wr * self.Radius / U
        tau_hydro = self.calculate_hydro_torque(self.Radius, U, self.CqFunc(lambda_))
        dw_dt = (tau_hydro / self.Ng - tau_g - self.B_d * w) / self.I_eff
        return dw_dt

    def simulate(self):
        """
        Simulates turbine dynamics and calculates performance metrics.

        Handles both closed-loop and open-loop dynamics based on rated torque limits.
        """
        print("Solving the initial value problem (IVP) for turbine dynamics...")

        # Initial angular velocity (rad/s)
        w0 = self.Ng * self.Uinf_adjusted[0] * self.TSROpt / self.Radius  

        # Solve the IVP for closed-loop dynamics
        solution = sp.integrate.solve_ivp(
            self.turbine_dynamics_closeloop, 
            [self.t[0], self.t[-1]], 
            [w0], 
            t_eval=self.t, 
            method='Radau'
        )

        # Store the results
        self.w = solution.y[0]  # Angular velocity over time
        self.wr = self.w / self.Ng
        self.Tg = self.Kopt * (self.wr)**2 / self.Ng
        self.Iq = self.Tg / self.Kt
        self.Vq = self.w * self.Kt - self.Rw * self.Iq

        # Check if the electrical power exceeds the rated power
        if np.any(self.Tg > self.Trated):
            print("At least one value in self.Tg is greater than self.Trated.")
            print("Rated torque exceeded. Switching to open-loop dynamics...")
            
            # Limit generator torque
            self.Tg = np.minimum(self.Tg, self.Trated)

            # Solve the IVP for open-loop dynamics
            solution = sp.integrate.solve_ivp(
                self.turbine_dynamics_openloop, 
                [self.t[0], self.t[-1]], 
                [w0], 
                t_eval=self.t, 
                method='Radau'
            )

            # Store the results
            self.w = solution.y[0]  # Angular velocity over time
            self.wr = self.w / self.Ng
            self.Iq = self.Tg / self.Kt
            self.Vq = self.w * self.Kt - self.Rw * self.Iq

        # Calculate TSR and other parameters
        self.TSR = self.wr * self.Radius / self.Uinf_adjusted
        self.Ft = self.calculate_thrust_force(self.Radius, self.Uinf_adjusted, self.CtFunc(self.TSR))
        self.Th = self.calculate_hydro_torque(self.Radius, self.Uinf_adjusted, self.CqFunc(self.TSR))

        # Calculate power metrics
        self.calculate_power()

        # Print indication that the IVP solving is complete
        print("IVP solving complete.")

    def calculate_Kopt(self):
        return 0.5 * self.GLOBAL.rho * (np.pi * self.Radius**2) * self.Radius**3 * self.CpOpt / self.TSROpt**3

    def calculate_hydro_torque(self, Radius, Uinf, Cq):
        return 0.5 * self.GLOBAL.rho * (np.pi * Radius**2) * Radius * Uinf**2 * Cq

    def calculate_thrust_force(self, Radius, Uinf, Ct):
        return 0.5 * self.GLOBAL.rho * (np.pi * Radius**2) * Uinf**2 * Ct

    def calculate_phydro(self, Uinf, Cp):
        return 0.5 * self.GLOBAL.rho * (np.pi * self.Radius**2) * Uinf**3 * Cp

    def calculate_pfluid(self):
        return 0.5 * self.GLOBAL.rho * (np.pi * self.Radius**2) * self.Uinf_adjusted**3

    def calculate_punc(self):
        return self.Kopt * (self.Uinf_adjusted * self.TSROpt / self.Radius)**3

    def calculate_pmech(self):
        return self.w * self.Tg

    def calculate_pelec(self):
        return self.Vq * self.Iq

    def calculate_power(self):
        self.Phydro = self.calculate_phydro(self.Uinf_adjusted, self.CpFunc(self.TSR))
        self.Pfluid = self.calculate_pfluid()
        self.Punc = self.calculate_punc()
        self.Pmech = self.calculate_pmech()
        self.Pelec = self.calculate_pelec()

    def get_results(self):
        """
        Retrieves simulation results for analysis.

        Returns:
            dict: Simulation results including time steps, angular velocity, torque, power metrics, and TSR.
        """
        return {
            't': self.t,
            'w': self.w,
            'wr': self.wr,
            'Tg': self.Tg,
            'Pmech': self.Pmech,
            'Pelec': self.Pelec,
            'Phydro': self.Phydro,
            'Pfluid': self.Pfluid,
            'Punc': self.Punc,
            'TSR': self.TSR,
            'Ft': self.Ft,
            'Th': self.Th,  
            'dHub': self.dHub_array, 
            'Uinf_adjusted': self.Uinf_adjusted
        }

    def flowAtDepth(self, FlowSpeed, Radius, dHub, dMoor):
        """
        Adjusts flow speed at a turbine's hub depth based on mooring depth and surface flow speed.

        Args:
            FlowSpeed (float or np.ndarray): Flow speed at the surface in m/s.
            Radius (float): Rotor radius in meters.
            dHub (float): Hub depth in meters.
            dMoor (float): Mooring depth in meters.

        Returns:
            float or np.ndarray: Adjusted flow speed at the hub depth in m/s.
        """
        if np.isscalar(FlowSpeed):
            FlowSpeed = np.array([FlowSpeed])
            dHub = np.array([dHub])

        Uout = np.zeros_like(FlowSpeed)
        Area = np.pi * Radius**2.0
        Uavg = FlowSpeed / 1.07
        dz = dMoor - dHub

        for i in range(len(FlowSpeed)):
            if (dz[i] - Radius) < 0.5 * dMoor and (dz[i] + Radius) <= 0.5 * dMoor:
                Za = dz[i] - Radius
                Zb = dz[i] + Radius
                Zc = Zd = 0.0
            elif (dz[i] - Radius) >= 0.5 * dMoor and (dz[i] + Radius) > 0.5 * dMoor:
                Za = Zb = 0.0
                Zc = dz[i] - Radius
                Zd = dz[i] + Radius
            else:
                Za = dz[i] - Radius
                Zb = Zc = 0.5 * dMoor
                Zd = dz[i] + Radius

            tempvalA = (1.1407 * (1 / dMoor)**(3 / 7) * Uavg[i]**3.0 * (Zb**(10 / 7) - Za**(10 / 7)))
            tempvalB = (1.07 * Uavg[i])**3.0 * (Zd - Zc)
            PfluidAvg = 1 / (4.0 * Radius) * self.GLOBAL.rho * Area * (tempvalA + tempvalB)
            Uout[i] = ((2.0 * PfluidAvg) / (self.GLOBAL.rho * Area))**(1 / 3.0)

        return Uout if len(Uout) > 1 else Uout[0]