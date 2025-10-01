"""
vital: A package for managing tidal energy systems, rotor simulations, vessel data, and more.

This package provides modules for:
- Handling tidal data
- Rotor simulations
- Constraint checking
- Vessel operations
- Levelized cost of energy (LCOE) calculations
- Battery charging systems

It also includes global physical constants and unit conversion constants for consistent calculations.
"""

from .constUnitConvert import ConstantsUnitConversion
from .constGlobal import ConstantsGlobal
from .module_tidal import TidalData
from .module_rotor import RotorData
from .module_rotor_simulation import RotorSimulation
from .module_constraint_checker import ConstraintChecker
from .module_vessel import VesselData
from .module_lcoe import LCOEData,LCOECalculator
from .module_lcoe_optimizer import LCOEOptimizer

# Initialize global constants for physical properties
GLOBAL = ConstantsGlobal()

# Initialize unit conversion constants
CONVERT = ConstantsUnitConversion()

# Expose the classes and constants directly
__all__ = [
    # Classes
    "TidalData",
    "RotorData",
    "RotorSimulation",
    "ConstraintChecker",
    "VesselData",
    "LCOEData",
    "LCOECalculator",
    "LCOEOptimizer",
    # Constants
    "CONVERT",
    "GLOBAL",
]