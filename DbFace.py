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
from DbEdge import DbEdge

class DbFace:
    def __init__(self, parent, face:adsk.fusion.BRepFace, commandInputsEdgeSelect):
        self.parent:DogboneCommand = parent
        self.face = face # BrepFace
        self._faceId = hash(face.entityToken)
        self.faceNormal = dbUtils.getFaceNormal(face)
        self._refPoint = face.nativeObject.pointOnFace if face.assemblyContext else face.pointOnFace
        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self._selected = True
        self._associatedEdgesDict = {} # Keyed with edge
        processedEdges = [] # used for quick checking if an edge is already included (below)

        #==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        #==============================================================================

        faceNormal = dbUtils.getFaceNormal(face)

        faceEdgesSet = {hash(edge.entityToken) for edge in face.edges}
        faceVertices = [vertex for vertex in face.vertices]
        allEdges = {}
        for vertex  in faceVertices:
            allEdges.update({hash(edge.entityToken): edge for edge in vertex.edges})

        candidateEdgesId = set(allEdges.keys()) - faceEdgesSet
        candidateEdges = [allEdges[edgeId] for edgeId in candidateEdgesId]

        # for edge in self.face.body.edges:
        for edge in candidateEdges:
            if not edge.isValid:
                continue
            if edge.isDegenerate:
                continue
            if edge in processedEdges:
                continue
            try:
                if edge.geometry.curveType != adsk.core.Curve3DTypes.Line3DCurveType:
                    continue
                vector:adsk.core.Vector3D = dbUtils.getEdgeVector(edge, refFace = face) #edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
                vector.normalize()
                if not vector.isParallelTo(faceNormal):
                    continue
                if vector.isEqualTo(faceNormal):
                    continue
                face1, face2 = edge.faces 
                if face1.geometry.objectType != adsk.core.Plane.classType():
                    continue
                if face2.geometry.objectType != adsk.core.Plane.classType():
                    continue              
                if abs(dbUtils.getAngleBetweenFaces(edge) - math.pi/2) > 0.001:
                    continue

                edgeId = hash(edge.entityToken) #str(edge.tempId)+':'+ activeEdgeName
                parent.selectedEdges[edgeId] = self._associatedEdgesDict[edgeId] = DbEdge(edge = edge, parentFace = self)
                processedEdges.append(edge)
                parent.addingEdges = True
                self.commandInputsEdgeSelect.addSelection(edge)
                parent.addingEdges = False
            except:
                dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))

    def __hash__(self):
        return self.faceId

    def __del__(self):
        pass

    @property
    def selectAll(self):
        self._selected = True
        self.parent.addingEdges = True
        [(selectedEdge.select, 
          _ui.activeSelections.add(selectedEdge.edge))
        for selectedEdge in self._associatedEdgesDict.values()]
        self.parent.addingEdges = False

    @property
    def deselectAll(self):
        self._selected = False
        self.parent.addingEdges = True
        [(selectedEdge.deselect, 
          _ui.activeSelections.removeByEntity(selectedEdge.edge))
          for selectedEdge in self._associatedEdgesDict.values()]
        self.parent.addingEdges = False

    @property
    def refPoint(self):
        return self._refPoint

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
    def edgeIdSet(self):
        return set(self._associatedEdgesDict.keys())
    
    @property
    def selectedEdges(self):
        return [edgeObj for edgeObj in self._associatedEdgesDict.values() if edgeObj.isSelected]
    
    @property
    def deleteEdges(self):
        [(_ui.activeSelections.removeByEntity(edgeObj.edge),
           self.parent.selectedEdges.pop(edgeId) )
           for edgeId, edgeObj in self._associatedEdgesDict.items()]
        del self._associatedEdgesDict

    @property
    def faceId(self):
        return self._faceId

    @property
    def component(self)->adsk.fusion.Component:
        return self.face.assemblyContext.component if self.face.assemblyContext else _rootComp
  
    @property
    def occurrence(self)->adsk.fusion.Occurrence:
        return self.face.assemblyContext if self.face.assemblyContext else None

    @property
    def native(self):
        return self.face.nativeObject if self.face.nativeObject else self.face

    def revalidate(self)->adsk.fusion.BRepFace:
        self._face =  self.component.findBRepUsingPoint(
                    self._refPoint, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False 
                    ).item(0)
        return self._face