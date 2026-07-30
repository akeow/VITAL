import numpy as np
from scipy.optimize import brute

from vital.module_rotor_simulation import RotorSimulation
from vital.module_vessel import VesselData
from vital.module_constraint_checker import ConstraintChecker
from vital.module_lcoe import LCOEData, LCOECalculator


class LCOEOptimizer:
    def __init__(self, tidal, rotor, base_config, user_vessel_properties):
        self.tidal = tidal
        self.rotor = rotor
        self.base_config = base_config.copy()
        self.user_vessel_properties = user_vessel_properties
        self._cache = {}

    def _build_config(self, variable_names, variable_values, fixed_params, site_params=None):
        """
        Build a full config dictionary by combining:
            - base_config
            - variable values
            - fixed parameters
            - site-specific parameters
        """
        config = self.base_config.copy()

        for name, value in zip(variable_names, variable_values):
            config[name] = value

        if fixed_params:
            config.update(fixed_params)

        if site_params:
            config.update(site_params)

        return config

    def _evaluate(self, variable_values, variable_names, fixed_params,
                site_params, customer, application, BatteryCapacity_kWh,
                lifetime, discount_rate, turbulence_intensity):
        """
        Evaluate one design point.
        """
        key = (
            tuple(np.atleast_1d(variable_values).tolist()),
            tuple(variable_names),
            tuple(sorted(fixed_params.items())) if fixed_params else (),
            customer,
            application,
            BatteryCapacity_kWh,
            lifetime,
            discount_rate,
            turbulence_intensity,
        )

        if key in self._cache:
            return self._cache[key]

        config = self._build_config(variable_names, variable_values, fixed_params, site_params)

        try:
            rotor_sim = RotorSimulation(config)
            rotor_sim.simulate()
            result = rotor_sim.get_results()

            vessel = VesselData(
                user_defined=True,
                vessel_properties=self.user_vessel_properties,
                simResult=result
            )

            checker = ConstraintChecker(self.rotor, config, vessel, result)
            constraints = {
                "Power Constraint": checker.check_power_constraint(),
                "Depth Constraint": checker.check_depth_constraint(),
                "Cavitation Constraint": checker.check_cavitation_constraint(),
                "Pitch Constraint": checker.check_pitch_constraint(),
            }

            if not all(constraints.values()):
                print("Constraint failure for:", dict(zip(variable_names, variable_values)))
                self._cache[key] = 1e6
                return 1e6

            data = LCOEData(
                self.tidal,
                config,
                vessel,
                result,
                lifetime=lifetime,
                discount_rate=discount_rate,
                turbulence_intensity=turbulence_intensity,
                customer=customer,
                application=application,
                BatteryCapacity_kWh=BatteryCapacity_kWh,
            )
            calculator = LCOECalculator(data)
            lcoe = calculator.calculate_lcoe()

            self._cache[key] = lcoe
            return lcoe

        except Exception as e:
            print("Evaluation failed for:", dict(zip(variable_names, variable_values)))
            print("Reason:", e)
            self._cache[key] = 1e6
            return 1e6

    def optimize(
        self,
        variable_bounds,
        fixed_params=None,
        site_params=None,
        customer="customer_B",
        application="battery_charging",
        BatteryCapacity_kWh=10.0,
        lifetime=10,
        discount_rate=0.1,
        turbulence_intensity=0.0,
    ):
        """
        Perform an explicit grid search over the specified variable bounds.

        Args:
            variable_bounds (dict): Dictionary mapping variable names to tuples of
                (min, max, step).
            fixed_params (dict, optional): Parameters to hold fixed during search.
            site_params (dict, optional): Site-specific parameters such as:
                - dMoor
                - Uinf
                - t
            customer (str): Customer key for LCOE model.
            application (str): Application key for LCOE model.
            BatteryCapacity_kWh (float): Battery capacity for battery charging.
            lifetime (int): Project lifetime in years.
            discount_rate (float): Discount rate.
            turbulence_intensity (float): Turbulence intensity.

        Returns:
            dict: Dictionary containing:
                - optimal_params
                - optimal_lcoe
                - results_table
                - feasible_table
                - variable_names
                - fixed_params
                - site_params
                - grid
        """
        import numpy as np
        import pandas as pd
        from itertools import product

        # Reset cache each run
        self._cache = {}

        if fixed_params is None:
            fixed_params = {}

        if site_params is None:
            site_params = {}

        variable_names = list(variable_bounds.keys())

        # Build value lists for each variable
        value_lists = []
        for name in variable_names:
            low, high, step = variable_bounds[name]
            values = np.arange(low, high + 0.5 * step, step)
            value_lists.append(values)

        results = []

        # Explicit grid search
        for combo in product(*value_lists):
            lcoe = self._evaluate(
                variable_values=combo,
                variable_names=variable_names,
                fixed_params=fixed_params,
                site_params=site_params,
                customer=customer,
                application=application,
                BatteryCapacity_kWh=BatteryCapacity_kWh,
                lifetime=lifetime,
                discount_rate=discount_rate,
                turbulence_intensity=turbulence_intensity,
            )

            print("Testing:", dict(zip(variable_names, combo)), "LCOE:", lcoe)

            result_row = {name: val for name, val in zip(variable_names, combo)}
            result_row["LCOE"] = lcoe
            results.append(result_row)

        results_df = pd.DataFrame(results)

        # Identify feasible results
        feasible_df = results_df[np.isfinite(results_df["LCOE"]) & (results_df["LCOE"] < 1e6)].copy()

        if feasible_df.empty:
            raise ValueError(
                "No feasible design found within the provided bounds. "
                "Try widening the search space or relaxing constraints."
            )

        # Find optimal row
        best_idx = feasible_df["LCOE"].idxmin()
        best_row = feasible_df.loc[best_idx]

        optimal_params = {name: best_row[name] for name in variable_names}
        optimal_lcoe = float(best_row["LCOE"])

        # Build a grid structure for plotting compatibility
        mesh = np.meshgrid(*value_lists, indexing="ij")
        z = results_df["LCOE"].to_numpy().reshape([len(v) for v in value_lists])

        grid = (
            optimal_params,
            optimal_lcoe,
            mesh,
            z,
        )

        return {
            "optimal_params": optimal_params,
            "optimal_lcoe": optimal_lcoe,
            "results_table": results_df,
            "feasible_table": feasible_df,
            "variable_names": variable_names,
            "fixed_params": fixed_params,
            "site_params": site_params,
            "grid": grid,
        }

    def plot_results(self, opt_result):
        """
        Plot optimization results from the explicit grid search.

        Behavior:
            - 1 variable: line plot
            - 2 variables: heatmap
            - 3 variables: 3 heatmaps, each holding one variable at its optimal value
            - 4+ variables: pairwise heatmaps, holding remaining variables at optimal values
        """
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns
        from itertools import combinations

        variable_names = opt_result["variable_names"]
        results_df = opt_result["results_table"]
        optimal = opt_result["optimal_params"]

        nvars = len(variable_names)

        print("Optimal parameters:")
        for k, v in optimal.items():
            print(f"  {k}: {v}")

        # Replace penalty values with NaN for plotting
        plot_df = results_df.copy()
        plot_df["LCOE"] = np.where(plot_df["LCOE"] >= 1e6, np.nan, plot_df["LCOE"])

        # ------------------------------------------------------------
        # 1 variable: line plot
        # ------------------------------------------------------------
        if nvars == 1:
            x_name = variable_names[0]

            df_sorted = plot_df.sort_values(by=x_name)

            plt.figure(figsize=(8, 4))
            plt.plot(df_sorted[x_name], df_sorted["LCOE"], marker="o")
            plt.xlabel(x_name)
            plt.ylabel("LCOE")
            plt.title("Optimization result")
            plt.grid(True)
            plt.tight_layout()
            plt.show()
            return

        # ------------------------------------------------------------
        # 2 variables: heatmap
        # ------------------------------------------------------------
        if nvars == 2:
            x_name, y_name = variable_names

            pivot = plot_df.pivot_table(
                index=y_name,
                columns=x_name,
                values="LCOE",
                aggfunc="mean"
            )

            plt.figure(figsize=(8, 6))
            sns.heatmap(pivot, annot=True, cmap="coolwarm", fmt=".2f")
            plt.xlabel(x_name)
            plt.ylabel(y_name)
            plt.title("LCOE heatmap")
            plt.tight_layout()
            plt.show()
            return

        # ------------------------------------------------------------
        # 3 variables: 3 heatmaps, one for each variable held fixed
        # ------------------------------------------------------------
        if nvars == 3:
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))

            for ax, fixed_name in zip(axes, variable_names):
                other_names = [name for name in variable_names if name != fixed_name]
                fixed_value = optimal[fixed_name]

                filtered = plot_df[np.isclose(plot_df[fixed_name], fixed_value)]

                pivot = filtered.pivot_table(
                    index=other_names[1],
                    columns=other_names[0],
                    values="LCOE",
                    aggfunc="mean"
                )

                sns.heatmap(pivot, annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
                ax.set_xlabel(other_names[0])
                ax.set_ylabel(other_names[1])
                ax.set_title(f"{fixed_name} fixed at optimal")

            plt.tight_layout()
            plt.show()
            return

        # ------------------------------------------------------------
        # 4+ variables: pairwise heatmaps with others fixed at optimum
        # ------------------------------------------------------------
        if nvars >= 4:
            pairs = list(combinations(variable_names, 2))
            nplots = len(pairs)

            ncols = 2
            nrows = int(np.ceil(nplots / ncols))

            fig, axes = plt.subplots(nrows, ncols, figsize=(8 * ncols, 5 * nrows))
            axes = np.atleast_1d(axes).flatten()

            for i, (x_name, y_name) in enumerate(pairs):
                ax = axes[i]

                filtered = plot_df.copy()
                for fixed_name in variable_names:
                    if fixed_name not in (x_name, y_name):
                        filtered = filtered[np.isclose(filtered[fixed_name], optimal[fixed_name])]

                pivot = filtered.pivot_table(
                    index=y_name,
                    columns=x_name,
                    values="LCOE",
                    aggfunc="mean"
                )

                sns.heatmap(pivot, annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
                ax.set_xlabel(x_name)
                ax.set_ylabel(y_name)
                ax.set_title(f"{x_name} vs {y_name}\n(others fixed at optimal)")

            # Hide unused axes if any
            for j in range(i + 1, len(axes)):
                axes[j].axis("off")

            plt.tight_layout()
            plt.show()
            return

        print("No plotting rule available for this optimization result.")