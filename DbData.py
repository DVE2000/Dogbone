# -*- coding: utf-8 -*-

from math import pi
from typing import Optional
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import adsk.core, adsk.fusion
from .DbClasses import _design
# from .py_packages.pydantic.dataclasses import dataclass

@dataclass_json
@dataclass
class DbParams:
     '''Dataclass - Holds add-in instance setup values'''
     toolDiaStr: str = "0.25 in"
     dbType: str = "Normal Dogbone"
     fromTop: bool = True
     toolDiaOffsetStr: str = "0 cm"

     mortiseType: bool = False
     longSide: bool = True

     minimalPercent: float = 10.0
     minAngleLimit: float = 5/180*pi
     maxAngleLimit: float = 3*pi/4

     parametric: bool = False
     expandModeGroup: bool = True
     expandSettingsGroup: bool = True    
     logging: int = 0
     benchmark: bool = False

     @property
     def toolDia(self):
          return _design.unitsManager.evaluateExpression(self.toolDiaStr)

     @property
     def toolDiaOffset(self):
          return  _design.unitsManager.evaluateExpression(self.toolDiaOffsetStr)
     
