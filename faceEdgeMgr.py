# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 19:51:42 2019

@author: Peter Ludikar
"""

import logging
 
from collections import defaultdict

import adsk.core, adsk.fusion
import traceback
import os
import weakref
import math

import time
from . import dbutils as dbUtils
from math import sqrt as sqrt

#constants - to keep attribute group and names consistent
DOGBONEGROUP = 'dogBoneGroup'
DBEDGE = 'dbEdge'
DBFACE = 'dbFace'
FACE_ID = 'faceID'
REV_ID = 'revId'
ID = 'id'
DEBUGLEVEL = logging.NOTSET



# Generate an edgeHash or faceHash from object
calcHash = lambda x: str(x.tempId) + ':' + x.assemblyContext.name.split(':')[-1] if x.assemblyContext else str(x.tempId) + ':' + x.body.name
#faceSelections = lambda selectionObjects: [face for face in selectionObjects if face.objectType == adsk.fusion.BRepFace.classType()]
#edgeSelections = lambda selectionObjects: [edge for edge in selectionObjects if edge.objectType == adsk.fusion.BRepEdge.classType()]
faceSelections = lambda selectionObjects: list(filter(lambda face: face.objectType == adsk.fusion.BRepFace.classType(), selectionObjects))
edgeSelections = lambda selectionObjects: list(filter(lambda edge: edge.objectType == adsk.fusion.BRepEdge.classType(), selectionObjects))
calcOccName = lambda x: x.assemblyContext.name if x.assemblyContext else x.body.name


class faceEdgeMgr:
#    TODO: deleteFace, addEdge, deleteEdge - properties: validateEntity
    def __init__(self):
        self.registeredFaces = []
        self.registeredEdges = []
        self.registeredComponents = []
        self.faces = []
        self._topFaces = {}
        self.selectedOccurrences = {} 
        self.selectedFaces = {} 
        self.selectedEdges = {}
        
    def addFace(self, face):
        activeOccurrenceName = calcOccName(face)
            
        faces = []
        faces = self.selectedOccurrences.get(activeOccurrenceName, faces)
        if faces:
            faceObject = self.selectedFaces[calcHash(face)]
            faceObject.selected = True
            for edge in faceObject.validEdgesAsDict.values():
                edge.selected = True
            return
        
        body = face.body
        faceNormal = dbUtils.getFaceNormal(face)
#        validFaces = {calcHash(face):SelectedFace(face, self) for face in body.faces if faceNormal.angleTo(dbUtils.getFaceNormal(face))==0}
        
        validFaces = {}
        for face1 in body.faces:
            if faceNormal.angleTo(dbUtils.getFaceNormal(face1))== 0:
                faceObject = SelectedFace(face1, self)
                if not faceObject.edgeCount:
                    del faceObject
                    continue
                validFaces.update({calcHash(face1): faceObject})
        self._topFaces.update({activeOccurrenceName: dbUtils.getTopFace(face)})
        self.selectedOccurrences.update({activeOccurrenceName: validFaces})
        self.selectedFaces.update(validFaces) # adds face(s) to a list of faces associated with this occurrence
        for faceObject in validFaces.values():
            self.selectedEdges.update(faceObject.selectedEdgesAsDict)
    
    def isSelectable(self, entity):
        entityHash = calcHash(entity)
        if entity.assemblyContext:
            self.activeOccurrenceName = entity.assemblyContext.component.name
        else:
            self.activeOccurrenceName = entity.body.name
        if self.activeOccurrenceName not in self.registeredComponents:
            return True
        return not ((entityHash not in self.registeredFaces) and (entityHash not in self.registeredEdges))
        
    @property        
    def selectedEdgesAsList(self):
         return [edgeObject.edge for edgeObject in self.selectedEdges.values()]   

    @property        
    def selectedEdgesAsGroupList(self):
        edgeList = []
        for occ in self.selectedOccurrences.values():
            occurrenceGroup = []
            for faceHash in occ:
                occurrenceGroup.extend(self.selectedFaces[faceHash].selectedEdgesAsList)
            edgeList.append(occurrenceGroup)
        return edgeList
            
#         return [edgeObject.edge for edgeObject in self.selectedEdges.values()]   

    @property        
    def selectedFacesAsList(self):
         return [faceObject.face for faceObject in self.selectedFaces.values()]   
                    
    def deleteFace(self, face):
#TODO:
        faceHash = calcHash(face)
        faceObject = self.selectedFaces[faceHash]
        edgesToBeDeleted = faceObject.edgesAsDict
        for edgeObject in edgesToBeDeleted.keys():
            
            self.selectedEdges.pop(edgeKey)
        del self.selectedFaces[faceHash]  #deleting faceObject inherently deletes associated edgeObjects
        
    def addEdge(self, edge):
        occurrenceName = calcOccName(edge)
        faceHashes = self.selectedOccurrences[occurrenceName] #get list of face Ids associated with this occurrence
        edgeHash = calcHash(edge)
        for faceHash in faceHashes:
            if edgeHash not in self.selectedFaces[faceHash]:
                continue
            self.selectedEdges[edgeHash].select = True
            break
            return True
        return False

class SelectedEdge:
    def __init__(self, edge, parentFace):
        self.edge = edge
        self.edgeHash = calcHash(edge)
        self.edgeName = edge.assemblyContext.component.name if edge.assemblyContext else edge.body.name
        self.tempId = edge.tempId
        self._selected = True
        self.parent = weakref.ref(parentFace)()
        self.selectedEdges = self.parent.parent.selectedEdges
        self.parent.parent.registeredEdges.append(self.edgeHash)
        
    def __del__(self):
        self.parent.registeredEdges.remove(self.edgeHash)

    @property
    def getFace(self):
        return self.parentFace
        
    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, x):
        self._selected = x
        


class SelectedFace:
    """
    This class manages a single Face:
    keeps a record of the viable edges, whether selected or not
    principle of operation: the first face added to a body/occurrence entity will find all other same facing faces, automatically finding eligible edges - they will all be selected by default.
    edges and faces have to be selected to be selected in the UI
    when all edges of a face have been deselected, the face becomes deselected
    when all faces of a body/entity have been deselected - the occurrence and all associated face and edge objects will be deleted and GC'd
    manages edges:
        edges can be selected or deselected individually
        faces can be selected or deselected individually
        first face selection will cause all other appropriate faces and corresponding edges on the body to be selected
        validEdges dict makes lists of candidate edges available
        each face or edge selection that is changed will reflect in the parent management object selectedOccurrences, selectedFaces and selectedEdges
    """

    def __init__(self, face, parent):  #None parent is temporary - should allow old moethod to still work!!
        self.face = face # BrepFace
        self.faceHash = calcHash(face)
        self.tempId = face.tempId
        self.parent = weakref.ref(parent)()
        self.selectedEdges = self.parent.selectedEdges if parent else {}
        
        self.parent.registeredFaces.append(self.faceHash)
        
        if face.assemblyContext:
            self.occurrenceName = face.assemblyContext.name
            self.componentName = face.assemblyContext.component.name
            self.parent.registeredComponents.append(self.componentName)
        else:
            self.occurrenceName = face.body.name
            self.componentName = self.occurrenceName
            self.parent.registeredComponents.append(self.componentName)

        self.parent.registeredComponents = list(set(self.parent.registeredComponents))  #clean up to ensure no duplicates - have to see if this adds too much overhead     
#        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self._selected = True # record of all valid faces are kept, but only ones that are selected==True are processed for dogbones???
        self.validEdges = {} # Keyed with edgeHash
#        self.edgeSelection = adsk.core.ObjectCollection.create()

        #==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        #==============================================================================

#        faceNormal = dbUtils.getFaceNormal(face)
        
        self.brepEdges = dbUtils.findInnerCorners(face) #get all candidate edges associated with this face
        
        for edge in self.brepEdges:
            if edge.isDegenerate:
                continue
            try:
                
                edgeObject = SelectedEdge(edge, self)
    
                self.validEdges[edgeObject.edgeHash] = edgeObject
            except:
                dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))
                
    def __del__(self):
        self.parent.registeredFaces.remove(self.faceHash)
        self.parent.registeredComponents.remove(self.occurrenceName)
        for edgeObject in self.validEdges.values():
            del edgeObject
                
    @property
    def validEdgesAsDict(self):
        return self.validEdges

    @property
    def validEdgesAsList(self):
        return [edgeObject.edge for edgeObject in self.validEdges.values()]

    @property
    def edgeCount(self):
        return len(self.validEdgesAsList)

    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, x):
        self._selected = x
        
    @property
    def selectedEdgesAsList(self):
        return [edge for edge in self.validEdges.values() if edge._selected]
        
    @property
    def selectedEdgesAsDict(self):
        return {edge for edge in self.validEdges.items() if edge[1]._selected}

    @property        
    def selectedEdgesAsCollection(self):
        collection = adsk.core.ObjectCollection.create()
        for edge in self.selectedEdgesAsList:
            collection.add(edge)
        return collection
        
    @property
    def topFace(self):
        return dbUtils.getTopFace(self.face)
        
    def addEdge(self, edge):
#        TODO:
        edgeObject = SelectedEdge(edge)
        self.validEdges[edgeObject.edgeHash] = edgeObject
        self.selectedEdges.update(self.validEdges)
        
        return edgeObject.edgeHash, edgeObject
