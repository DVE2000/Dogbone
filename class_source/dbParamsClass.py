# -*- coding: utf-8 -*-

from math import pi
import hashlib
import json 
from dataclasses import dataclass
from abc import ABC, abstractclassmethod
from typing import Optional

#==============================================================================
# Would have used namedtuple, but it doesn't play nice with json - so have to do it longhand
#==============================================================================
@dataclass
class DbParams():
     toolDia: float = 0.25,
     dbType: str = "Normal Dogbone",
     fromTop: bool = False,
     toolDiaOffset: int = 0,
     offset: int = 0,
     minimalPercent: float = 0,
     longSide: bool = True,
     minAngleLimit: float = pi/4,
     maxAngleLimit: float = 3*pi/4

     @property
     def jsonStr(self):
          return json.dumps(self.dbParams)
          
     @jsonStr.setter
     def jsonStr(self, jsonStr):
     #        TODO may need to do a consistency check on the imported resuls - just in case the json string is from an older version of the addin
          self.dbParams = json.loads(jsonStr)