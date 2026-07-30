"""
module_rotor_simulation.py

This module provides tools for simulating rotor dynamics and calculating
turbine performance metrics, including mechanical power, electrical power,
speed, torque, and thrust force.

Key Features:
    * Simulate turbine dynamics under varying flow speeds and depths.
    * Calculate hydro torque, thrust force, and power metrics
      (mechanical, electrical, fluid).
    * Handle closed-loop and open-loop turbine dynamics.
    * Adjust flow speed based on hub depth and mooring depth.
    * Support multiple power-conversion models, including:
        - a built-in simple generator electrical model
        - optional user-supplied generator loss models
        - optional user-supplied power electronics loss models
    * Retrieve simulation results for analysis and visualization.
"""
import numpy as np
from vital.constGlobal import ConstantsGlobal
import scipy as sp


class RotorSimulation:
    """
    A class for simulating rotor dynamics and calculating turbine
    performance metrics.
    """
    # Attributes:
    #     Radius (float): Rotor radius in meters.
    #     Prated (float): Rated power in watts.
    #     Trated (float): Rated torque in Nm.
    #     dHub (float): Hub depth in meters.
    #     dMoor (float): Mooring depth in meters.
    #     Uinf (np.ndarray): Flow speeds at the surface in m/s.
    #     t (np.ndarray): Time steps for the simulation.
    #     CpFunc (function): Function to calculate Cp (power coefficient) based on TSR.
    #     CqFunc (function): Function to calculate Cq (torque coefficient) based on TSR.
    #     CtFunc (function): Function to calculate Ct (thrust coefficient) based on TSR.
    #     CpOpt (float): Optimal Cp value.
    #     TSROpt (float): Optimal TSR value corresponding to CpOpt.
    #     TSRmax (float): Maximum TSR value where Cp or Ct becomes zero.
    #     Ng (float): Gear ratio.
    #     J_d (float): Drivetrain inertia.
    #     B_d (float): Drivetrain friction.
    #     J_r (float): Rotor inertia.
    #     I_eff (float): Effective inertia of the system.
    #     power_model (str): Selected power-conversion model.
    #     generator_loss_model (callable or None): Optional user-supplied generator loss model.
    #     pe_loss_model (callable or None): Optional user-supplied PE loss model.
    #     Kt (float or None): Generator torque constant used in simple electrical-model modes.
    #     Rw (float or None): Generator resistance used in simple electrical-model modes.
    #     GLOBAL (ConstantsGlobal): Global constants for physical properties.

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
        self.Uinf = np.asarray(config['Uinf'], dtype=float)
        self.t = np.asarray(config['t'], dtype=float)
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

        if self.Ng <= 0:
            raise ValueError("Ng must be positive.")
        if self.Radius <= 0:
            raise ValueError("Radius must be positive.")
        if len(self.t) < 2:
            raise ValueError("Time vector t must contain at least two points.")

        self.I_eff = self.J_r / self.Ng**2 + self.J_d  # Effective inertia

        # Optional power-conversion model selection
        self.power_model = config.get('power_model', 'simple')
        self.generator_loss_model = config.get('generator_loss_model', None)
        self.pe_loss_model = config.get('pe_loss_model', None)

        # Built-in simple generator electrical model parameters
        self.Kt = config.get('Kt', None)
        self.Rw = config.get('Rw', None)

        self.GLOBAL = ConstantsGlobal()
        self.Kopt = self.calculate_Kopt()

        self.initialize_results()
        self.dHub_array = np.ones(np.shape(self.t)) * self.dHub
        self.Uinf_adjusted = self.flowAtDepth(
            self.Uinf, self.Radius, self.dHub_array, self.dMoor
        )

        valid_power_models = [
            'simple',
            'simple_with_pe_loss',
            'generator_loss_model',
            'generator_and_pe_loss_models'
        ]
        if self.power_model not in valid_power_models:
            raise ValueError(
                f"Invalid power_model '{self.power_model}'. "
                f"Choose from {valid_power_models}."
            )

        if self.power_model in ['simple', 'simple_with_pe_loss']:
            if self.Kt is None or self.Rw is None:
                raise ValueError(
                    f"power_model='{self.power_model}' requires 'Kt' and 'Rw' in config."
                )

        if self.power_model == 'simple_with_pe_loss':
            if self.pe_loss_model is None or not callable(self.pe_loss_model):
                raise ValueError(
                    "power_model='simple_with_pe_loss' requires 'pe_loss_model' callable."
                )

        if self.power_model == 'generator_loss_model':
            if self.generator_loss_model is None or not callable(self.generator_loss_model):
                raise ValueError(
                    "power_model='generator_loss_model' requires 'generator_loss_model' callable."
                )

        if self.power_model == 'generator_and_pe_loss_models':
            if (
                self.generator_loss_model is None
                or not callable(self.generator_loss_model)
                or self.pe_loss_model is None
                or not callable(self.pe_loss_model)
            ):
                raise ValueError(
                    "power_model='generator_and_pe_loss_models' requires both "
                    "'generator_loss_model' and 'pe_loss_model' callables."
                )

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

        self.Pmech = np.zeros(np.shape(self.t))
        self.Pelec = np.zeros(np.shape(self.t))
        self.Pac = np.zeros(np.shape(self.t))
        self.Pbat = np.zeros(np.shape(self.t))
        self.Pgen_loss = np.zeros(np.shape(self.t))
        self.Ppe_loss = np.zeros(np.shape(self.t))
        self.Phydro = np.zeros(np.shape(self.t))
        self.Pfluid = np.zeros(np.shape(self.t))
        self.Punc = np.zeros(np.shape(self.t))

        self.Iq = np.zeros(np.shape(self.t))
        self.Vq = np.zeros(np.shape(self.t))

    def turbine_dynamics_closeloop(self, t, w):
        """
        Defines the ODE system for closed-loop turbine dynamics.

        Parameters
        ----------
        t : float
            Current simulation time.
        w : array_like
            Generator-side angular speed state vector [rad/s].

        Returns
        -------
        list
            Time derivative of generator-side angular speed.
        """
        w = w[0]
        U = float(np.interp(t, self.t, self.Uinf_adjusted))
        U = max(U, 1e-6)

        wr = w / self.Ng
        lambda_ = wr * self.Radius / U
        tau_hydro = self.calculate_hydro_torque(self.Radius, U, self.CqFunc(lambda_))
        tau_g = self.Kopt * wr**2 / self.Ng

        dw_dt = (tau_hydro / self.Ng - tau_g - self.B_d * w) / self.I_eff
        return [dw_dt]

    def turbine_dynamics_openloop(self, t, w):
        """
        Defines the ODE system for open-loop turbine dynamics.

        Parameters
        ----------
        t : float
            Current simulation time.
        w : array_like
            Generator-side angular speed state vector [rad/s].

        Returns
        -------
        list
            Time derivative of generator-side angular speed.
        """
        w = w[0]
        U = float(np.interp(t, self.t, self.Uinf_adjusted))
        U = max(U, 1e-6)

        tau_g = np.interp(t, self.t, self.Tg)
        wr = w / self.Ng
        lambda_ = wr * self.Radius / U
        tau_hydro = self.calculate_hydro_torque(self.Radius, U, self.CqFunc(lambda_))

        dw_dt = (tau_hydro / self.Ng - tau_g - self.B_d * w) / self.I_eff
        return [dw_dt]

    def simulate(self):
        """
        Simulates turbine dynamics and calculates turbine performance metrics.

        The rotor and drivetrain dynamics are solved first. The selected
        ``power_model`` is then used to calculate electrical power and optional
        generator or power-electronics losses.

        The closed-loop turbine dynamics use an optimal torque law. If the
        resulting generator torque exceeds ``Trated``, the torque trajectory is
        clipped and the dynamics are re-solved in open-loop mode.

        Notes:
            User-supplied generator and power-electronics loss models are
            assumed to use generator-side angular speed ``self.w`` and
            generator torque ``self.Tg``.

        Returns:
            None
        """
        print("Solving the initial value problem (IVP) for turbine dynamics...")

        # Initial generator-side angular velocity (rad/s), chosen from the
        # optimal TSR condition at the initial adjusted flow speed.
        w0 = self.Ng * self.Uinf_adjusted[0] * self.TSROpt / self.Radius

        # Solve closed-loop turbine dynamics first
        solution = sp.integrate.solve_ivp(
            self.turbine_dynamics_closeloop,
            [self.t[0], self.t[-1]],
            [w0],
            t_eval=self.t,
            method='Radau'
        )
        if not solution.success:
            raise RuntimeError(f"Closed-loop dynamics solve failed: {solution.message}")

        # Closed-loop solution
        self.w = solution.y[0]          # generator-side angular velocity
        self.wr = self.w / self.Ng      # rotor-side angular velocity
        self.Tg = self.Kopt * (self.wr)**2 / self.Ng

        # For simple electrical-model modes, compute generator electrical variables
        if self.power_model in ['simple', 'simple_with_pe_loss']:
            self.Iq = self.Tg / self.Kt
            self.Vq = self.w * self.Kt - self.Rw * self.Iq

        # If rated torque is exceeded, clip torque and re-simulate in open loop
        if np.any(self.Tg > self.Trated):
            print("Rated torque exceeded. Switching to open-loop dynamics...")

            # Limit generator torque to the rated torque and use this fixed
            # torque trajectory for the open-loop re-simulation.
            self.Tg = np.minimum(self.Tg, self.Trated)

            solution = sp.integrate.solve_ivp(
                self.turbine_dynamics_openloop,
                [self.t[0], self.t[-1]],
                [w0],
                t_eval=self.t,
                method='Radau'
            )
            if not solution.success:
                raise RuntimeError(f"Open-loop dynamics solve failed: {solution.message}")

            # Open-loop solution
            self.w = solution.y[0]
            self.wr = self.w / self.Ng

            # In open-loop mode, self.Tg remains the clipped torque trajectory.
            if self.power_model in ['simple', 'simple_with_pe_loss']:
                self.Iq = self.Tg / self.Kt
                self.Vq = self.w * self.Kt - self.Rw * self.Iq

        # Compute TSR and hydrodynamic loads
        U_safe = np.maximum(self.Uinf_adjusted, 1e-6)
        self.TSR = self.wr * self.Radius / U_safe
        self.Ft = self.calculate_thrust_force(
            self.Radius, self.Uinf_adjusted, self.CtFunc(self.TSR)
        )
        self.Th = self.calculate_hydro_torque(
            self.Radius, self.Uinf_adjusted, self.CqFunc(self.TSR)
        )

        # Compute power quantities according to the selected power model
        self.calculate_power()

        print("IVP solving complete.")


    def calculate_Kopt(self):
        """
        Calculates the optimal torque-law constant for TSR tracking.

        Returns
        -------
        float
            Optimal torque constant used in the closed-loop control law.

        Raises
        ------
        ValueError
            If the optimal tip-speed ratio is not positive.
        """
        if self.TSROpt <= 0:
            raise ValueError("TSROpt must be positive to compute Kopt.")

        return (
            0.5
            * self.GLOBAL.rho
            * (np.pi * self.Radius**2)
            * self.Radius**3
            * self.CpOpt
            / self.TSROpt**3
        )

    def calculate_hydro_torque(self, Radius, Uinf, Cq):
        """
        Calculates the hydrodynamic torque exerted on the turbine.

        Parameters
        ----------
        Radius : float
            Rotor radius in meters.
        Uinf : float or np.ndarray
            Flow speed in m/s.
        Cq : float or np.ndarray
            Torque coefficient.

        Returns
        -------
        float or np.ndarray
            Hydrodynamic torque in N m.
        """
        return 0.5 * self.GLOBAL.rho * (np.pi * Radius**2) * Radius * Uinf**2 * Cq

    def calculate_thrust_force(self, Radius, Uinf, Ct):
        """
        Calculates the thrust force exerted on the turbine.

        Parameters
        ----------
        Radius : float
            Rotor radius in meters.
        Uinf : float or np.ndarray
            Flow speed in m/s.
        Ct : float or np.ndarray
            Thrust coefficient.

        Returns
        -------
        float or np.ndarray
            Thrust force in N.
        """
        return 0.5 * self.GLOBAL.rho * (np.pi * Radius**2) * Uinf**2 * Ct

    def calculate_phydro(self, Uinf, Cp):
        """
        Calculates extracted hydrodynamic power.

        Parameters
        ----------
        Uinf : float or np.ndarray
            Flow speed in m/s.
        Cp : float or np.ndarray
            Power coefficient.

        Returns
        -------
        float or np.ndarray
            Extracted hydrodynamic power in W.
        """
        return 0.5 * self.GLOBAL.rho * (np.pi * self.Radius**2) * Uinf**3 * Cp

    def calculate_pfluid(self):
        """
        Calculates available fluid power based on adjusted flow speed.

        Returns
        -------
        np.ndarray
            Available fluid power in W.
        """
        return 0.5 * self.GLOBAL.rho * (np.pi * self.Radius**2) * self.Uinf_adjusted**3

    def calculate_punc(self):
        """
        Calculates unconstrained power based on the optimal torque law.

        Returns
        -------
        np.ndarray
            Unconstrained power estimate in W.
        """
        return self.Kopt * (self.Uinf_adjusted * self.TSROpt / self.Radius)**3

    def calculate_pmech(self):
        """
        Calculates generator-side mechanical power.

        Returns
        -------
        np.ndarray
            Mechanical power in W, computed as generator torque times
            generator-side angular speed.
        """
        return self.w * self.Tg

    def calculate_pelec(self):
        """
        Calculates electrical power using the built-in simple generator model.

        Notes
        -----
        This quantity is only used in the simple electrical-model modes.

        Returns
        -------
        np.ndarray
            Electrical power in W.
        """
        return self.Vq * self.Iq 

    def calculate_power(self):
        """
        Calculates hydrodynamic, mechanical, electrical, and loss quantities.

        Supported power models are:

        ``simple``
            Uses the built-in generator electrical model based on ``Kt`` and
            ``Rw``. No power-electronics loss model is applied.

        ``simple_with_pe_loss``
            Uses the built-in generator electrical model and then applies a
            user-supplied power-electronics loss model.

        ``generator_loss_model``
            Uses a user-supplied generator loss model to compute AC-side power
            from mechanical power. No power-electronics loss model is applied.

        ``generator_and_pe_loss_models``
            Uses user-supplied generator and power-electronics loss models to
            compute AC-side and battery-side power.

        Notes:
            In user-supplied loss-model modes, losses are assumed to be
            functions of generator-side angular speed and generator torque.
            For compatibility with downstream code, ``Pelec`` is used as the
            primary electrical output. In generator-loss-model modes, ``Pelec``
            is equal to ``Pac``.
        """
        # --------------------------------------------------------------
        # Always compute hydrodynamic and mechanical-side quantities
        # --------------------------------------------------------------
        self.Phydro = self.calculate_phydro(self.Uinf_adjusted, self.CpFunc(self.TSR))
        self.Pfluid = self.calculate_pfluid()
        self.Punc = self.calculate_punc()
        self.Pmech = self.calculate_pmech()

        # --------------------------------------------------------------
        # Reset outputs before applying the selected power model
        # --------------------------------------------------------------
        self.Pelec[:] = 0.0
        self.Pac[:] = 0.0
        self.Pbat[:] = 0.0
        self.Pgen_loss[:] = 0.0
        self.Ppe_loss[:] = 0.0

        # User-supplied loss equations are assumed to use generator-side
        # speed and torque.
        omega_g = self.w
        tau_g = self.Tg

        # --------------------------------------------------------------
        # Mode 1: built-in simple generator electrical model only
        # --------------------------------------------------------------
        if self.power_model == 'simple':
            # Iq and Vq are computed in simulate() for simple-model modes.
            self.Pelec = self.calculate_pelec()
            self.Pac = np.maximum(0.0, self.Pelec.copy())

            # No PE loss model supplied; assume battery-side power equals
            # AC-side power.
            self.Pbat = self.Pac.copy()

        # --------------------------------------------------------------
        # Mode 2: built-in generator model + user-supplied PE loss model
        # --------------------------------------------------------------
        elif self.power_model == 'simple_with_pe_loss':
            # Iq and Vq are computed in simulate() for simple-model modes.
            self.Pelec = self.calculate_pelec()
            self.Pac = np.maximum(0.0, self.Pelec.copy())

            self.Ppe_loss = np.asarray(self.pe_loss_model(omega_g, tau_g), dtype=float)
            self.Ppe_loss = np.maximum(0.0, self.Ppe_loss)

            self.Pbat = np.maximum(0.0, self.Pac - self.Ppe_loss)

        # --------------------------------------------------------------
        # Mode 3: user-supplied generator loss model only
        # --------------------------------------------------------------
        elif self.power_model == 'generator_loss_model':
            self.Pgen_loss = np.asarray(self.generator_loss_model(omega_g, tau_g), dtype=float)
            self.Pgen_loss = np.maximum(0.0, self.Pgen_loss)

            self.Pac = np.maximum(0.0, self.Pmech - self.Pgen_loss)

            # For compatibility with existing code, treat AC-side power as
            # the electrical output in this mode.
            self.Pelec = self.Pac.copy()

            # No PE loss model supplied; assume battery-side power equals
            # AC-side power.
            self.Pbat = self.Pac.copy()

            # The simple generator electrical variables are not used in this mode.
            self.Iq[:] = np.nan
            self.Vq[:] = np.nan

        # --------------------------------------------------------------
        # Mode 4: user-supplied generator loss model + PE loss model
        # --------------------------------------------------------------
        elif self.power_model == 'generator_and_pe_loss_models':
            self.Pgen_loss = np.asarray(self.generator_loss_model(omega_g, tau_g), dtype=float)
            self.Pgen_loss = np.maximum(0.0, self.Pgen_loss)

            self.Pac = np.maximum(0.0, self.Pmech - self.Pgen_loss)

            self.Ppe_loss = np.asarray(self.pe_loss_model(omega_g, tau_g), dtype=float)
            self.Ppe_loss = np.maximum(0.0, self.Ppe_loss)

            self.Pbat = np.maximum(0.0, self.Pac - self.Ppe_loss)

            # For compatibility with existing code, treat AC-side power as
            # the electrical output in this mode.
            self.Pelec = self.Pac.copy()

            # The simple generator electrical variables are not used in this mode.
            self.Iq[:] = np.nan
            self.Vq[:] = np.nan

        else:
            raise ValueError(f"Unsupported power_model: {self.power_model}")
        


    def get_results(self):
        """
        Retrieves simulation results for analysis.

        Returns
        -------
        dict
            Dictionary containing time histories of:
                - simulation time
                - generator-side and rotor-side speeds
                - generator torque
                - hydrodynamic loads
                - hydrodynamic, mechanical, and electrical power quantities
                - optional generator and PE loss terms
                - AC-side and battery-side output power
                - generator electrical variables for simple-model modes

        Notes
        -----
        - `w` is generator-side angular speed.
        - `wr` is rotor-side angular speed.
        - In loss-model modes, `Pelec` is taken to be equal to `Pac`
          for compatibility with existing downstream code.
        """
        return {
            # Time and operating states
            't': self.t,
            'w': self.w,                  # generator-side angular speed
            'wr': self.wr,                # rotor-side angular speed
            'Tg': self.Tg,                # generator torque
            'TSR': self.TSR,

            # Hydrodynamic loads
            'Ft': self.Ft,
            'Th': self.Th,

            # Site / operating conditions
            'dHub': self.dHub_array,
            'Uinf_adjusted': self.Uinf_adjusted,

            # Power quantities
            'Phydro': self.Phydro,
            'Pfluid': self.Pfluid,
            'Punc': self.Punc,
            'Pmech': self.Pmech,
            'Pelec': self.Pelec,          # equals Pac in loss-model modes
            'Pac': self.Pac,
            'Pbat': self.Pbat,

            # Optional subsystem loss terms
            'Pgen_loss': self.Pgen_loss,
            'Ppe_loss': self.Ppe_loss,

            # Built-in generator electrical model variables
            'Iq': self.Iq,
            'Vq': self.Vq,

            # Metadata
            'power_model': self.power_model,
        }

    def flowAtDepth(self, FlowSpeed, Radius, dHub, dMoor):
        """
        Adjusts flow speed at turbine hub depth based on mooring depth and
        surface flow speed.

        Parameters
        ----------
        FlowSpeed : float or np.ndarray
            Flow speed at the surface in m/s.
        Radius : float
            Rotor radius in meters.
        dHub : float or np.ndarray
            Hub depth in meters.
        dMoor : float
            Mooring depth in meters.

        Returns
        -------
        float or np.ndarray
            Adjusted flow speed at hub depth in m/s.
        """
        scalar_input = np.isscalar(FlowSpeed)

        FlowSpeed = np.atleast_1d(np.asarray(FlowSpeed, dtype=float))
        dHub = np.atleast_1d(np.asarray(dHub, dtype=float))

        if len(dHub) not in [1, len(FlowSpeed)]:
            raise ValueError("dHub must be scalar or have the same length as FlowSpeed.")

        if len(dHub) == 1 and len(FlowSpeed) > 1:
            dHub = np.full_like(FlowSpeed, dHub[0], dtype=float)

        Uout = np.zeros_like(FlowSpeed, dtype=float)
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

            tempvalA = (
                1.1407 * (1 / dMoor)**(3 / 7) * Uavg[i]**3.0 * (Zb**(10 / 7) - Za**(10 / 7))
            )
            tempvalB = (1.07 * Uavg[i])**3.0 * (Zd - Zc)
            PfluidAvg = 1 / (4.0 * Radius) * self.GLOBAL.rho * Area * (tempvalA + tempvalB)
            Uout[i] = ((2.0 * PfluidAvg) / (self.GLOBAL.rho * Area))**(1 / 3.0)

        return Uout[0] if scalar_input else Uout