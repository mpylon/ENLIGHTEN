import logging
import os

from enum import IntEnum
from pyexpat import ExpatError

log = logging.getLogger(__name__)

"""
Namespace containing various enums and constants used elsewhere within the 
application.

@todo consider making "common" a package (directory), and each of these classes
      can be modules (files) within it
"""
VERSION = "3.2.32"

""" ENLIGHTEN's application version number (checked by scripts/deploy and bootstrap.bat) """

class Views(IntEnum):
    SCOPE               = 0
    SETTINGS            = 1
    HARDWARE            = 2
    ABSORBANCE          = 3
"""
It's important to keep this list in sync with the comboBox_view items.
@todo consider auto-populating inside code
"""

class ViewsHelper:
    pretty_names = {
        Views.HARDWARE:     "Hardware",
        Views.SCOPE:        "Scope",
    }

    def get_pretty_name(n):
        return ViewsHelper.pretty_names.get(n, "UNKNOWN")

    def parse(s):
        s = s.upper()
        if "HARDWARE"             in s: return Views.HARDWARE
        if "SCOPE"                in s: return Views.SCOPE
        if "RAMAN"                in s: return Views.RAMAN
        if "ABS"                  in s: return Views.ABSORBANCE
        if "TRANS" in s or "REFL" in s: return Views.TRANSMISSION
        log.error("Invalid view: %s", s)
        return Views.SCOPE

class OperationModes(IntEnum):
    RAMAN     = 0
    NON_RAMAN = 1
    EXPERT    = 2

class OperationModesHelper:
    def parse(s):
        s = s.upper()
        if "SETUP"   in s: return OperationModes.SETUP
        if "CAPTURE" in s: return OperationModes.CAPTURE
        log.error("Invalid operation mode: %s", s)
        return OperationModes.SETUP

class Pages(IntEnum):
    HARDWARE_SETTINGS     = 0
    HARDWARE_CAPTURE      = 1
    SPEC_SETTINGS         = 2
    SPEC_CAPTURE          = 3

class Axes(IntEnum):
    PIXELS      = 0
    WAVELENGTHS = 1
    WAVENUMBERS = 2
    COUNTS      = 3
    PERCENT     = 4
    AU          = 5

class AxesHelper:
    ## HTML for Qt
    pretty_names = {
        Axes.PIXELS      : "pixel",
        Axes.WAVELENGTHS : "wavelength (nm)",
        Axes.WAVENUMBERS : "wavenumber (cm&#8315;&#185;)", # cm⁻¹
        Axes.COUNTS      : "intensity (counts)",
        Axes.PERCENT     : "percent (%)",
        Axes.AU          : "absorbance (AU)",
    }

    ## Unicode (not sure these are used)
    suffixes = {
        Axes.PIXELS      : "px",
        Axes.WAVELENGTHS : "nm",
        Axes.WAVENUMBERS : "cm⁻¹",
        Axes.COUNTS      : "",
        Axes.PERCENT     : "%",
        Axes.AU          : "AU",
    }

    def get_pretty_name(n): return AxesHelper.pretty_names.get(n, "Unknown")
    def get_suffix     (n): return AxesHelper.suffixes    .get(n, "??")

class LaserPowerUnits(IntEnum):
    PERCENT     = 0
    MILLIWATT   = 1

def get_default_data_dir():
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), "Documents", "EnlightenSpectra")
    return os.path.join(os.environ["HOME"], "EnlightenSpectra")
