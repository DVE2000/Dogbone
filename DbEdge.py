import logging
 
from collections import defaultdict

import adsk.core, adsk.fusion
import math
import traceback
import os
import json

import time
from . import dbutils as dbUtils
from .decorators import eventHandler
from math import sqrt as sqrt

class DbEdge:
    def __init__(self, edge:adsk.fusion.BRepEdge, parentFace:DbFace):
        self.edge = edge
        self._edgeId = hash(edge.entityToken)
        self._selected = True
        self._parentFace = parentFace
        self._native = self.edge.nativeObject if self.edge.nativeObject else self.edge

        face1, face2 = (face for face in self._native.faces)
        _,face1normal = face1.evaluator.getNormalAtPoint(face1.pointOnFace)
        _,face2normal = face2.evaluator.getNormalAtPoint(face2.pointOnFace)
        face1normal.add(face2normal)
        face1normal.normalize()
        self._cornerVector = face1normal

        self._dogboneCentre = self.native.startVertex.geometry \
            if self.native.startVertex in self._parentFace.native.vertices \
            else self.native.endVertex.geometry
        
        self._endPoints = (self.native.startVertex, self.native.endVertex)\
                if self.native.startVertex in self._parentFace.native.vertices\
                    else (self.native.endVertex, self.native.startVertex)

    def __hash__(self):
        return self._edgeId

    @property
    def select(self):
        self._selected = True

    @property
    def deselect(self):
        self._selected = False

    @property
    def isSelected(self):
        return self._selected

    @property
    def native(self):
        return self._native

    @property
    def dogboneCentre(self)->adsk.core.Point3D:
        '''
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        '''
        return self._dogboneCentre

    @property
    def endPoints(self)->adsk.fusion.BRepVertex:
        '''
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        '''
        return self._endPoints

    @property
    def cornerVector(self)->adsk.core.Vector3D:
        '''
        returns normalised vector away from the faceVertex that 
        the dogbone needs to be located on
          '''
        return self._cornerVector 
    
    def faceObj(self):
        return self._parentFace
    
    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, DbEdge):
            return __o.hash == self._hash
        if isinstance(__o, str):
            return hash(__o) == self._hash
        if isinstance(__o, adsk.fusion.BRepEdge):
            return __o == self._edge
        return NotImplemented
    
    def __hash__(self) -> int:
        return self._hash

    @property
    def native(self):
        return self.edge.nativeObject if self.edge.nativeObject else self.edge

