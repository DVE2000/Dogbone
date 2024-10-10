# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

# Peter completely revamped the dogbone add-in by Casey Rogers and Patrick Rainsberry and David Liu
# Some of the original utilities have remained, but a lot of the other functionality has changed.

# The original add-in was based on creating sketch points and extruding - Peter found using sketches and extrusion to be very heavy
# on processing resources, so this version has been designed to create dogbones directly by using a hole tool. So far the
# the performance of this approach is day and night compared to the original version.

# Select the face you want the dogbones to drop from. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diameter equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.
import os
import sys

import adsk.core
import adsk.fusion

_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f"{_appPath}", "py_packages")

if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    
from . import commands

CONFIG_PATH = os.path.join(_appPath, "defaults.dat")

# noinspection PyMethodMayBeStatic

def run(context):
    commands.start()

def stop(context):
    # _ui.terminateActiveCommand()
    adsk.terminate()
    commands.stop()

# In memory of Caroline
