Overview
========

The **Vessel Integrated Turbine Assessment for LCOE (VITAL)** software is designed to assess the Levelized Cost of Energy (LCOE) for tidal turbines integrated with vessels or floating platforms. VITAL provides tools for managing tidal data, rotor performance maps, vessel specifications, rotor simulations, constraint checking, and LCOE calculations.

Tutorials and Workflow
======================

.. image:: VITAL_ModuleOverview.png
   :alt: Overview of how each module and data interact with one another.
   :width: 800px
   :align: center

The figure above illustrates how the modules and data interact within VITAL.

Below are tutorials prepared for each module, demonstrating their intended use and workflow:

Tidal Data (`module_tidal`)
---------------------------
This tutorial explains how to acquire tidal data and site information, including flow speed, mooring depth, and other parameters, using NOAA Tidal and Current APIs.  
**Example**: `Tutorial1`_

Rotor Data (`module_rotor`)
---------------------------
This tutorial guides users on defining rotor performance curves (e.g., Cp vs TSR and Ct vs TSR) using a text file in the intended format. The module fits equations to the rotor data for use in simulations.  
**Example**: `Tutorial2`_

Rotor Simulation (`module_rotor_simulation`)
--------------------------------------------
This tutorial demonstrates how to simulate rotor dynamics using tidal data (`Tutorial1`_) and rotor performance characteristics (`Tutorial2`_). Users will define turbine configuration parameters such as radius, power rating, hub depth, friction, resistance, and torque constant. The module calculates dynamic forces and speeds, ensuring the design is feasible. It assumes the use of an optimal TSR tracking controller.  
**Example**: `Tutorial3`_

Vessel Data (`module_vessel`) and Constraint Checker (`module_constraint_checker`)
--------------------------------------------
This tutorial explains how to use the output from `Tutorial3`_ to define vessel properties and check constraints. The module ensures the design meets operational requirements, such as:
  
- Ensuring electrical power remains within the generator's power rating.
- Verifying the rotor avoids cavitation.
- Confirming the rotor is submerged sufficiently to avoid excessive vessel drag while maintaining efficiency.

**Example**: `Tutorial4`_

For detailed information about how constraints for cavitation and pitch are implemented, refer to the `Constraint Documentation`_.


Levelized Cost of Energy (`module_lcoe`)
----------------------------------------
This tutorial shows how to calculate LCOE using results from Tutorials 1 to 3 and user-defined cost models and metrics.  
**Example**: `Tutorial5`_

Brute Force Optimization (`module_lcoe_optimizer`)
--------------------------------------------------
This tutorial demonstrates how to perform a grid search for parameters such as radius, power rating, hub depth, and the number of turbines. The module simulates the system, calculates LCOE, checks constraints, and identifies feasible configurations with the lowest LCOE.  
**Example**: `Tutorial6`_

API Documentation
------------------

For detailed information about each module, refer to the `API Documentation`_.

.. _Tutorial1: examples/Tutorial1_Tidal.ipynb
.. _Tutorial2: examples/Tutorial2_Rotor.ipynb
.. _Tutorial3: examples/Tutorial3_SimulateRotor.ipynb
.. _Tutorial4: examples/Tutorial4_CheckConstraint.ipynb
.. _Tutorial5: examples/Tutorial5_CalculateCost.ipynb
.. _Tutorial6: examples/Tutorial6_BruteOptimization.ipynb
.. _API Documentation: api_docs/vital.html
.. _Constraint Documentation: constraint.html