import numpy as np
from scipy.optimize import brute

# Import high-level functions and data classes
from vital.module_tidal import process_tidal_data
from vital.module_rotor import RotorData
from vital.module_rotor_simulation import RotorSimulation
from vital.module_vessel import VesselData
from vital.module_constraint_checker import ConstraintChecker
from vital.module_lcoe import LCOEData, LCOECalculator


class LCOEOptimizer:
    """
    A class to optimize the Levelized Cost of Energy (LCOE) for tidal energy systems.

    Attributes:
        tidal (object): Tidal data object containing site-specific information.
        rotor (object): Rotor data object containing rotor-specific properties.
        config (dict): Configuration dictionary for simulation parameters.
        user_vessel_properties (dict): User-defined vessel properties.
    """

    def __init__(self, tidal, rotor, config, user_vessel_properties):
        """
        Initializes the LCOEOptimizer with tidal, rotor, configuration, and vessel properties.

        Args:
            tidal (object): Tidal data object containing site-specific information.
            rotor (object): Rotor data object containing rotor-specific properties.
            config (dict): Configuration dictionary for simulation parameters.
            user_vessel_properties (dict): User-defined vessel properties for.
        """
        self.tidal = tidal
        self.rotor = rotor
        self.config = config
        self.user_vessel_properties = user_vessel_properties

    def lcoe_objective(self, params):
        """
        Objective function for LCOE optimization. Simulates the rotor and calculates LCOE.

        Args:
            params (tuple): Tuple containing optimization parameters (radius, prated, dHub, numTurbine).

        Returns:
            float: Calculated LCOE value or a high penalty value if constraints are violated.
        """
        radius, prated, dHub, numTurbine = params
        self.config.update({'Radius': radius, 'Prated': prated, 'dHub': dHub, 'number_of_turbines': numTurbine})

        try:
            rotor_sim = RotorSimulation(self.config)
            rotor_sim.simulate()
            result = rotor_sim.get_results()

            vessel = VesselData(
                user_defined=True,
                vessel_properties=self.user_vessel_properties,
                simResult=result
            )

            constraint_checker = ConstraintChecker(self.rotor, self.config, vessel, result)

            constraints = {
                "Power Constraint": constraint_checker.check_power_constraint(),
                "Depth Constraint": constraint_checker.check_depth_constraint(),
                "Cavitation Constraint": constraint_checker.check_cavitation_constraint(),
                "Pitch Constraint": constraint_checker.check_pitch_constraint()
            }

            # Print violated constraints
            violated_constraints = [name for name, satisfied in constraints.items() if not satisfied]
            if violated_constraints:
                print(f"Configuration Failed: Radius={radius:.2f}, Prated={prated:.2f}, dHub={dHub:.2f}, numTurbine={numTurbine:.2f}")
                print(f"Violated Constraints: {', '.join(violated_constraints)}")
                return 1e6  # Penalty for invalid configurations  

            data = LCOEData(
                self.tidal, self.config, vessel, result,
                lifetime=10,  # Correct argument name
                discount_rate=0.1,
                turbulence_intensity=0.0,
                customer='customer_B',
                application='battery_charging',
                BatteryCapacity_kWh=10.0
            )
            calculator = LCOECalculator(data)
            lcoe = calculator.calculate_lcoe()

            return lcoe

        except Exception as e:
            print(f"Error during simulation or LCOE calculation: {e}")
            return 1e6  # Return a high penalty value in case of failure

    def optimize(self, bounds):
        """
        Performs brute force optimization to find the optimal parameters for minimizing LCOE.

        Args:
            bounds (dict): Dictionary containing parameter ranges for optimization.
                Keys: 'Radius', 'Prated', 'dHub', 'numTurbine'.
                Values: Tuples specifying the range (min, max) for each parameter.

        Returns:
            tuple: Optimal parameters, optimal LCOE value, and full optimization grid.
        """
        # Validate bounds
        if not all(key in bounds for key in ['Radius', 'Prated', 'dHub', 'numTurbine']):
            raise ValueError("Bounds must include 'Radius', 'Prated', 'dHub', and 'numTurbine'.")

        try:
            # Perform brute force optimization
            grid = brute(
                self.lcoe_objective,
                ranges=(bounds['Radius'], bounds['Prated'], bounds['dHub'], bounds['numTurbine']),
                full_output=True,
                finish=None,
                workers=-1,  # Use all available CPU cores
                disp=True,  # Print convergence messages
            )

            optimal_params = grid[0]
            optimal_lcoe = grid[1]

            print(f"Optimal Parameters: Radius={optimal_params[0]:.2f}, Prated={optimal_params[1]:.2f}, dHub={optimal_params[2]:.2f}, numTurbine={optimal_params[3]:.2f}")
            print(f"Optimal LCOE: {optimal_lcoe:.2f}")

            return optimal_params, optimal_lcoe, grid

        except Exception as e:
            print(f"Error during optimization: {e}")
            return None, None, None

    def plot_heatmaps(self, brute_output, bounds):
        """
        Generates heatmaps for visualizing the optimization results.

        Args:
            brute_output (tuple): Output from the brute force optimization containing parameter grids and LCOE values.
            bounds (dict): Dictionary containing parameter ranges for optimization.
                Keys: 'Radius', 'Prated', 'dHub', 'numTurbine'.
                Values: Tuples specifying the range (min, max) for each parameter.

        Returns:
            None: Displays heatmaps for parameter combinations.
        """
        import pandas as pd
        import seaborn as sns
        import matplotlib.pyplot as plt
        from itertools import combinations

        try:
            # Extract dimensions from brute_output following the order in bounds
            dimensions = {}
            for i, key in enumerate(bounds.keys()):
                dimensions[key] = brute_output[2][i]  # Extract dimension data in the same order as bounds

            # Extract z values (objective function values)
            z_values = brute_output[3]
            # Replace high penalty values (e.g., 1e6) with np.nan for visualization
            z_values = np.where(z_values >= 1e6, np.nan, z_values)

            # Map dimensions to indices based on the order in bounds
            dimension_indices = {key: i for i, key in enumerate(bounds.keys())}

            # Flatten all dimensions and z values into a big DataFrame
            data_flat = {
                key: dimensions[key].flatten() for key in dimensions.keys()
            }
            data_flat["z"] = z_values.flatten()  # Add z values to the DataFrame
            data = pd.DataFrame(data_flat)

            # Iterate through all pairs of dimensions
            for dim1, dim2 in combinations(dimensions.keys(), 2):
                # Find optimal values for dim1 and dim2 using dimension indices
                optimal_dim1 = brute_output[0][dimension_indices[dim1]]  # Extract optimal value for dim1
                optimal_dim2 = brute_output[0][dimension_indices[dim2]]  # Extract optimal value for dim2

                # Filter rows where dim1 and dim2 are at their optimal values
                filtered_data = data[(data[dim1] == optimal_dim1) & (data[dim2] == optimal_dim2)]

                # Select remaining dimensions for pivot table
                remaining_dims = [d for d in dimensions.keys() if d not in [dim1, dim2]]
                if len(remaining_dims) != 2:
                    continue  # Skip if there aren't exactly two remaining dimensions

                # Form pivot table using the remaining dimensions
                pivot_table = filtered_data.pivot_table(
                    values="z",
                    index=remaining_dims[0],
                    columns=remaining_dims[1]
                )

                # Plot the heatmap
                plt.figure(figsize=(8, 6))
                sns.heatmap(pivot_table, annot=True, cmap="coolwarm", fmt=".2f")

                # Add labels and title
                plt.title(f"LCOE for {remaining_dims[0]} vs {remaining_dims[1]} (Optimal {dim1}={optimal_dim1}, {dim2}={optimal_dim2})")
                plt.xlabel(remaining_dims[1])
                plt.ylabel(remaining_dims[0])

                # Show the plot
                plt.show()

        except Exception as e:
            print(f"Error during heatmap plotting: {e}")