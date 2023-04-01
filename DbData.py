# -*- coding: utf-8 -*-

from math import pi
from typing import Optional
from dataclasses import dataclass
from dataclasses_json import dataclass_json
# from .py_packages.pydantic.dataclasses import dataclass

@dataclass_json
@dataclass
class DbParams:
     '''Dataclass - Holds add-in instance setup values'''
     toolDia: float = 0.25
     dbType: str = "Normal Dogbone"
     # fromTop: bool = False
     fromTop: bool = True
     toolDiaOffset: int = 0
     toolDiameterOffset: int = 0
     offStr: str = "0 cm"
     offVal: float = 0.0
     toolDiaStr: str = "0.25 in"
     toolDiaVal: float = 0.635
     minimalPercent: float = 0
     longSide: bool = True
     minAngleLimit: float = 5/180*pi
     maxAngleLimit: float = 3*pi/4
     benchmark: bool = False
     minimalPercent: float = 10.0
     parametric: bool = False
     logging: int = 0
     mortiseType: bool = False
     expandModeGroup: bool = True
     expandSettingsGroup: bool = True    
 
     # @property
     # def toolDiaStr(self):
     #      return str(self.toolDia)
     # @property
     # def toolDiameterOffsetStr(self):
     #      return str(self.toolDiameterOffset)
