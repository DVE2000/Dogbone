# -*- coding: utf-8 -*-

from math import pi
import json 

#==============================================================================
# Would have used namedtuple, but it doesn"t play nice with json - so have to do it longhand
#==============================================================================
class DbParams():
    dbParams = {}
    def __init__(self,
                 toolDia = 0.25,
                 dbType = "Normal Dogbone",
                 fromTop = False,
                 toolDiaOffset = 0,
                 offset = 0,
                 minimalPercent = 0,
                 longSide = True,
                 minAngleLimit = pi/4,
                 maxAngleLimit = 3*pi/4
                 ):
                 
         self.dbParams["toolDia"] = toolDia
         self.dbParams["dbType"] =  dbType
         self.dbParams["fromTop"] =  fromTop
         self.dbParams["toolDiaOffset"] =  toolDiaOffset
         self.dbParams["offset"] = offset
         self.dbParams["minimalPercent"] =  minimalPercent
         self.dbParams["longSide"] = longSide
         self.dbParams["minAngleLimit"] = minAngleLimit  
         self.dbParams["maxAngleLimit"] =  maxAngleLimit
         
    @property
    def toolDia(self):
        return self.dbParams["toolDia"]
         
    @toolDia.setter
    def toolDia(self, toolDia):
        self.dbParams["toolDia"] =toolDia

    @property
    def dbType(self):
        return self.dbParams["dbType"]

    @dbType.setter
    def dbType(self, dbType):
        self.dbParams["dbType"] =dbType

    @property
    def fromTop(self):
         return self.dbParams["fromTop"]

    @fromTop.setter
    def fromTop(self, fromTop):
         self.dbParams["fromTop"] =fromTop

    @property
    def toolDiaOffset(self):
         return self.dbParams["toolDiaOffset"]
         
    @toolDiaOffset.setter
    def toolDiaOffset(self, toolDiaOffset):
         self.dbParams["toolDiaOffset"] =toolDiaOffset
         
    @property
    def offset(self):
         return self.dbParams["offset"]
         
    @offset.setter
    def offset(self, _offset):
         self.dbParams["offset"] = _offset
         
    @property
    def minimalPercent(self):
         return self.dbParams["minimalPercent"]
         
    @minimalPercent.setter
    def minimalPercent(self, minimalPercent):
         self.dbParams["minimalPercent"] =minimalPercent

    @property
    def longSide(self):
         return self.dbParams["longSide"]
         
    @longSide.setter
    def longSide(self, longSide):
         self.dbParams["longSide"] = longSide

    @property
    def minAngleLimit(self):
         return self.dbParams["minAngleLimit"]
         
    @minAngleLimit.setter
    def minAngleLimit(self, minAngleLimit):
         self.dbParams["minAngleLimit"] =minAngleLimit

    @property
    def maxAngleLimit(self):
         return self.dbParams["maxAngleLimit"]
         
    @maxAngleLimit.setter
    def maxAngleLimit(self, maxAngleLimit):
         self.dbParams["maxAngleLimit"] =maxAngleLimit
         
    @property
    def jsonStr(self):
         return json.dumps(self.dbParams)
         
    @jsonStr.setter
    def jsonStr(self, jsonStr):
#        TODO may need to do a consistency check on the imported resuls - just in case the json string is from an older version of the addin
         self.dbParams = json.loads(jsonStr)
         
    @property
    def isValid(self, paramToCheck):
#     TODO  presently just does a key check, doesn't check value type - may or may not be neccessary in the futue
        for key in self.dbParams.keys():
            if key in paramToCheck:
                continue
            return False
        return True               