# -*- coding: utf-8 -*-

from math import pi
import hashlib
import json 
# from dataclasses import dataclass
from abc import ABC, abstractclassmethod
from typing import Optional
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

class DbParams(BaseModel, allow_mutation = False):
     '''Dataclass - Holds add-in instance setup values'''
     toolDia: float = 0.25
     dbType: str = "Normal Dogbone"
     fromTop: bool = False
     toolDiaOffset: int = 0
     offset: int = 0
     minimalPercent: float = 0
     longSide: bool = True
     minAngleLimit: float = pi/4
     maxAngleLimit: float = 3*pi/4

     toolDiaStr = str(toolDia)
     offsetStr = str(offset)

@dataclass
class LoginLevels:
     '''Sets Loggong levels'''
     Notset: int = 0
     Debug: int = 10
     Info: int = 20
     Warning: int = 30
     Error:int = 40