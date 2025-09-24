# vital/__init__.py

# Import constants (if needed globally)
from .constUnitConvert import ConstantsUnitConversion
from .constGlobal import ConstantsGlobal

# Import modules
from .module_tidal import TidalData
from .module_rotor import RotorData
from .module_rotor_simulation import RotorSimulation
from .module_constraint_checker import ConstraintChecker
from .module_vessel import VesselData
from .module_lcoe import LCOE
from .module_battery_charging import BatteryCharging

# Initialize constants (if needed globally)
CONVERT = ConstantsUnitConversion()
GLOBAL = ConstantsGlobal()

# Expose the classes and constants directly
__all__ = [
    "TidalData",
    "RotorData",
    "RotorSimulation",
    "ConstraintChecker",
    "VesselData",
    "LCOE",
    "BatteryCharging",
    "CONVERT",
    "GLOBAL",
]