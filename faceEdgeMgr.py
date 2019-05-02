# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 19:51:42 2019

@author: Peter Ludikar
"""

import logging
from pprint import pformat

import operator

from collections import defaultdict

import adsk.core, adsk.fusion
import traceback
import os
import weakref
from functools import reduce, lru_cache

import time
from . import dbutils as dbUtils
from math import sqrt

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

faceSelections = lambda selectionObjects: list(filter(lambda face: face.objectType == adsk.fusion.BRepFace.classType(), selectionObjects))
edgeSelections = lambda selectionObjects: list(filter(lambda edge: edge.objectType == adsk.fusion.BRepEdge.classType(), selectionObjects))
calcOccName = lambda x: x.assemblyContext.name if x.assemblyContext else x.body.name


class FaceEdgeMgr:
#    TODO: deleteFace, addEdge, deleteEdge
    def __init__(self):
        self.logger = logging.getLogger('dogbone.mgr')
        
        self.logger.info('---------------------------------{}---------------------------'.format('faceEdgeMgr'))
        self.logger.debug('faceEdgeMgr initiated')
        self.registeredFaces = {} #key: occurrenceName value: faceObjects
        self.registeredEdges = {} #key: faceHash value: edgeObjects
        self.registeredComponents = [] #flat list of all components that have been registered
        self.faces = []
        self._topFaces = {} #key: occurrenceName value:topFace tuple
        self.selectedOccurrences = {} #key: occurrenceName value: list of selected Faces
        self.selectedFaces = {} #key: occurrenceName value: list of faceObjects
        self.selectedEdges = {} #key: faceHash value: list of edgeObjects
        
    def addFace(self, face):
        activeOccurrenceName = calcOccName(face)
            
        faces = self.selectedOccurrences.setdefault(activeOccurrenceName, [])
        self.logger.debug('cache cleared')
        self.completeEntityList.cache_clear()
        if faces:
            faceObject = self.selectedFaces[calcHash(face)]
            faceObject.selected = True

            return
        
        body = face.body
        faceNormal = dbUtils.getFaceNormal(face)
#        validFaces = {calcHash(face):SelectedFace(face, self) for face in body.faces if faceNormal.angleTo(dbUtils.getFaceNormal(face))==0}
        
#        validFaces = {}
        for face1 in body.faces:
            if faceNormal.angleTo(dbUtils.getFaceNormal(face1))== 0:
                faceObject = SelectedFace(face1, self)
        self._topFaces.update({activeOccurrenceName: dbUtils.getTopFace(face)})
        
    def deleteFace(self, face):
#TODO:
        self.logger.debug('registered Faces before = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces before = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges before = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges before = {}'.format(pformat(self.selectedEdges)))
        occHash = calcOccName(face)
        faceHash = calcHash(face)
        faceObjectList = self.selectedFaces[occHash]
        faceObject = list(filter(lambda x: x.faceHash == faceHash, faceObjectList))[0]
        faceObject.selected = False
        if not self.selectedFaces[occHash]:
            del self.selectedFaces[occHash]
            self.registeredComponents.remove(occHash)
            for faceObject in self.registeredFaces[occHash]:
                del faceObject
        self.logger.debug('registered Faces after = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces after = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges after = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges after = {}'.format(pformat(self.selectedEdges)))
        self.completeEntityList.cache_clear()
        self.logger.debug('cache cleared')
    
    @lru_cache(maxsize=128)
    def completeEntityList(self, dummy):  #dummy is only there to fool the lru_cache - it needs hashable parameters in the arguments
        self.logger.debug('registered Faces = {}'.format(len(list(self.registeredFacesAsList))))
        self.logger.debug('registered Edges = {}'.format(len(list(self.registeredEdgesAsList))))
        return not ((self._entity not in self.registeredFacesAsList) and (self._entity not in self.registeredEdgesAsList))
            

    def isSelectable(self, entity):
        
        self._entity = entity

        if entity.assemblyContext:
            self.activeOccurrenceName = entity.assemblyContext.component.name
        else:
            self.activeOccurrenceName = entity.body.name
        if self.activeOccurrenceName not in self.registeredComponents:
            return True

        return self.completeEntityList(1)
        
    @property        
    def registeredEdgesAsList(self):
        try:
            return map(lambda edgeObjects: edgeObjects.edge, reduce(operator.iadd, self.registeredEdges.values()))
        except:
            return []

    @property        
    def registeredFacesAsList(self):
        try:
            return map(lambda faceObjects: faceObjects.face, reduce(operator.iadd, self.registeredFaces.values()))
        except:
            return []
        
    @property
    def registeredEntitiesAsList(self):
        try:
            faceEntities = map(lambda faceObjects: faceObjects.face, reduce(operator.iadd, self.registeredFaces.values()))
            edgeEntities = map(lambda edgeObjects: edgeObjects.edge, reduce(operator.iadd, self.registeredEdges.values()))
            return faceEntities + edgeEntities
        except:
            return []


    @property
    def selectedEdgesAsList(self):
        try:
            return map(lambda edgeObjects: edgeObjects.edge, reduce(operator.iadd, self.selectedEdges.values()))
        except:
            return []    
            
    @property        
    def selectedFacesAsList(self):
        if not self.registeredFaces.values():
            return []
        return map(lambda faceObjects: faceObjects.face, reduce(operator.iadd, self.selectedFaces.values()))
                     
    @property        
    def selectedEdgesAsGroupList(self):
        return self.selectedEdges

        
#    def addEdge(self, edge):
#        occurrenceName = calcOccName(edge)
#        faceHashes = self.selectedOccurrences[occurrenceName] #get list of face Ids associated with this occurrence
#        edgeHash = calcHash(edge)
#        for faceHash in faceHashes:
#            if edgeHash not in self.selectedFaces[faceHash]:
#                continue
#            self.selectedEdges[edgeHash].select = True
#            break
#            return True
#        return False

class SelectedEdge:
    def __init__(self, edge, parentFace):
        self.logger = logging.getLogger('dogbone.mgr.edge')
        self.logger.info('---------------------------------{}---------------------------'.format('creating edge'))
        self.edge = edge
        self.edgeHash = calcHash(edge)
        self.edgeName = edge.assemblyContext.component.name if edge.assemblyContext else edge.body.name
        self.tempId = edge.tempId
        self.parent = weakref.ref(parentFace)()
        self.selectedEdges = self.parent.selectedEdges
        self.registeredEdges = self.parent.registeredEdges.append(self)
        self.selected = True #invokes selected property
        self.logger.debug('{} - edge initiated'.format(self.edgeHash))
        
    def __del__(self):
        self.logger.debug('edge {} deleted'.format(self.edgeHash))
#TODO:
        self.registeredEdges.remove[self.edge]
        self.logger.debug('{} - edge deleted'.format(self.edgeHash))
        if not self.registeredEdges:
            del self.parent.registeredEdges[self.parent.faceHash]
            self.logger.debug('{} - registered edge dict deleted'.format(self.edgeHash))


    @property
    def getFace(self):
        return self.parentFace
        
    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, selected):
        self.logger.debug('{} - edge {}'.format(self.edgeHash, 'selected' if selected else 'deselected'))
        self.logger.debug('before selected edge count for face {} = []'.format(self.parent.faceHash, len(self.selectedEdges)))
        if selected:
            self.selectedEdges.append(self)
            self.logger.debug('{} - edge appended to selectedEdges'.format(self.edgeHash))
        else: 
            self.selectedEdges.remove(self)
            self.logger.debug('{} - edge removed from selectedEdges'.format(self.edgeHash))
#            if not self.selectedEdges:  #if no edges left then deselect parent face
#                self._selected = False
#                self.parent.selected = False
#                del self.parent.selectedEdges[self.parent.faceHash]
#                logger.debug('{} - Face removed from selectedEdges'.format(self.parent.faceHash))
#                del self.parent.selectedFaces[self.parent.faceHash]  #
        self._selected = selected
        self.logger.debug('after selected edge count for face {} = []'.format(self.parent.faceHash, len(self.selectedEdges)))
        


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

    def __init__(self, face, parent):
        self.logger = logging.getLogger('dogbone.mgr.edge')

        self.logger.info('---------------------------------{}---------------------------'.format('creating face'))
        self.face = face # BrepFace
        self.faceHash = calcHash(face)
        self.tempId = face.tempId
        self._selected = True # record of all valid faces are kept, but only ones that are selected==True are processed for dogbones???
        self.parent = weakref.ref(parent)()

        self.occurrenceName = calcOccName(face)
        
        self.registeredFaces = self.parent.registeredFaces.setdefault(self.occurrenceName, [])#.append(self.face)
        self.registeredFaces.append(self)
        self.registeredEdges = self.parent.registeredEdges.setdefault(self.faceHash, [])
        self.registeredComponents = self.parent.registeredComponents
        
#        self._topFaces = self.parent._topFaces.setdefault(self.faceHash, [])

        self.selectedOccurrences = self.parent.selectedOccurrences.setdefault(self.occurrenceName, [])
        self.selectedFaces = self.parent.selectedFaces.setdefault(self.occurrenceName, [])
#        self.selectedFaces.append(self)
        
        self.selectedEdges = self.parent.selectedEdges.setdefault(self.faceHash, [])
        self.logger.debug('{} - face initiated'.format(self.faceHash))

#        self.registeredFaces.append(face)
        
        if face.assemblyContext:
            self.componentName = face.assemblyContext.component.name
        else:
            self.componentName = self.occurrenceName
            
        if self.componentName not in self.registeredComponents:

            self.registeredComponents.append(self.componentName)

#        self.registeredComponents = list(set(self.registeredComponents))  #clean up to ensure no duplicates - have to see if this adds too much overhead     
#        self.validEdges = {} # Keyed with edgeHash
#        self.edgeSelection = adsk.core.ObjectCollection.create()

        #==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        #==============================================================================

#        faceNormal = dbUtils.getFaceNormal(face)

        self.brepEdges = dbUtils.findInnerCorners(face) #get all candidate edges associated with this face
        self.logger.debug('{} - edges found on face creation'.format(len(self.brepEdges)))
        if not self.brepEdges:
#            self.selected = False
            self.logger.debug('no edges found on deselecting face '.format(self.faceHash))
            return
        
        for edge in self.brepEdges:
            if edge.isDegenerate:
                continue
            try:
                
                edgeObject = SelectedEdge(edge, self)
                self.logger.debug(' {} - edge object added'.format(edgeObject.edgeHash))
    
#                self.validEdges[edgeObject.edgeHash] = edgeObject
            except:
                dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))
        self.selected = True #invokes selected property
        self.logger.debug('registered component count = {}'.format(len(self.registeredComponents)))

        
                
    def __del__(self):
        self.logger.debug("face {} deleted".format(self.faceHash))
        self.registeredFaces.remove(self.face)
#        self.parent.registeredComponents.remove(self.occurrenceName)
        del self.selectedFaces[self.faceHash]
        self.logger.debug(' {} - face key deleted from registeredFaces'.format(self.faceHash))
        self.logger.debug('registered component count = {}'.format(len(self.registeredComponents)))
        for edgeObject in self.registeredEdges.values():
            del edgeObject
            self.logger.debug(' {} - edge object deleted'.format(edgeObject.edgeHash))
        del self.parent.registeredEdges[self.faceHash]
        self.logger.debug('registered Faces count = {}'.format(len(self.registeredFaces)))               
        self.logger.debug('selected Faces count = {}'.format(len(self.selectedFaces)))               
        self.logger.debug('registered edges count = {}'.format(len(self.registeredEdges)))               
        self.logger.debug('selected edges count = {}'.format(len(self.selectededEdges)))               
    @property
    def validEdgesAsDict(self):
        return self.selectedEdges

    @property
    def validEdgesAsList(self):
        return self.selectedEdges

    @property
    def edgeCount(self):
        return len(self.selectedEdges)

    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, selected):
        if not selected:
            self.selectedFaces.remove(self)
            self.logger.debug(' {} - face object removed from selectedFaces'.format(self.faceHash))
        else:
            self.selectedFaces.append(self)
            self.logger.debug(' {} - face object added to registeredFaces'.format(self.faceHash))

        for edge in self.registeredEdges:
            edge.selected = selected
            self.logger.debug(' {} - edge object selected - {}'.format(edge.edgeHash, selected))
#        if not self.selectedEdges:
#            self.selectedFaces.remove(self)
#            self._selected = False
#            logger.debug(' {} - face object removed from selectedFaces'.format(self.faceHash))
        else:    
            self._selected = selected
        
    @property
    def selectedEdgesAsList(self):
        return self.selectedEdges
        
    @property
    def selectedEdgesAsDict(self):
        return self.selectedEdges

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
