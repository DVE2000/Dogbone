# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 19:51:42 2019

@author: Peter Ludikar
"""

import logging

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

logging.shutdown()
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(lineno)s ; %(funcName)s ; %(levelname)s ; %(lineno)d; %(message)s')
appPath = os.path.dirname(os.path.abspath(__file__))
#        if not os.path.isfile(os.path.join(self.appPath, 'dogBone.log')):
#            return
logHandler = logging.FileHandler(os.path.join(appPath, 'dogbone_registry.log'), mode='w')
logHandler.setFormatter(formatter)
logHandler.flush()
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)


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
        logger.debug('faceEdgeMgr initiated')
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
#                if not faceObject.edgeCount:
#                    faceObject.selected = False
#                    continue
#                validFaces.update({calcHash(face1): face1})
        self._topFaces.update({activeOccurrenceName: dbUtils.getTopFace(face)})
#        self.selectedOccurrences.update({activeOccurrenceName: validFaces})
#        self.selectedFaces.update(validFaces) # adds face(s) to a list of faces associated with this occurrence
#        for faceObject in validFaces.values():
#            self.selectedEdges.update(faceObject.selectedEdgesAsDict)
    
    def isSelectable(self, entity):
        entityHash = calcHash(entity)
        if entity.assemblyContext:
            self.activeOccurrenceName = entity.assemblyContext.component.name
        else:
            self.activeOccurrenceName = entity.body.name
        if self.activeOccurrenceName not in self.registeredComponents:
            return True
        return not ((entity not in self.registeredFacesAsList) and (entity not in self.registeredEdgesAsList))
        
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

    def deleteFace(self, face):
#TODO:
        occHash = calcOccName(face)
        faceHash = calcHash(face)
        faceObjectList = self.selectedFaces[occHash]
        faceObject = list(filter(lambda x: x.faceHash == faceHash, faceObjectList))[0]
        faceObject.selected = False
        

#        del self.selectedFaces[faceHash]  #deleting faceObject inherently deletes associated edgeObjects
        
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
        self.edge = edge
        self.edgeHash = calcHash(edge)
        self.edgeName = edge.assemblyContext.component.name if edge.assemblyContext else edge.body.name
        self.tempId = edge.tempId
        self.parent = weakref.ref(parentFace)()
        self.selectedEdges = self.parent.selectedEdges
        self.registeredEdges = self.parent.registeredEdges.append(self)
        self.selected = True #invokes selected property
        logger.debug('{} - edge initiated'.format(self.edgeHash))
        
    def __del__(self):
        print('deleted edge {}'.format(self.edgeHash))
#TODO:
        self.registeredEdges.remove[self.edge]
        logger.debug('{} - edge deleted'.format(self.edgeHash))
        if not self.registeredEdges:
            del self.parent.registeredEdges[self.parent.faceHash]
            logger.debug('{} - registered edge dict deleted'.format(self.edgeHash))


    @property
    def getFace(self):
        return self.parentFace
        
    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, selected):
        logger.debug('{} - edge selected - {}'.format(self.edgeHash, selected))
        if selected:
            self.selectedEdges.append(self)
            logger.debug('{} - edge appended'.format(self.edgeHash))
        else: 
            self.selectedEdges.remove(self)
            logger.debug('{} - edge removed'.format(self.edgeHash))
            if not self.selectedEdges:  #if no edges left then deselect parent face
#                self._selected = False
                self.parent.selected = False
                del self.parent.selectedEdges[self.parent.faceHash]
                logger.debug('{} - Face removed from selectedEdges'.format(self.parent.faceHash))
#                del self.parent.selectedFaces[self.parent.faceHash]  #
        self._selected = selected
        


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
        logger.debug('{} - face initiated'.format(self.faceHash))

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

        self.selected = True #invokes selected property
        
        self.brepEdges = dbUtils.findInnerCorners(face) #get all candidate edges associated with this face
        logger.debug('{} - edges found on face creation'.format(len(self.brepEdges)))
        if not self.brepEdges:
            self.selected = False
            logger.debug('no edges found on deselecting face '.format(self.faceHash))
        
        for edge in self.brepEdges:
            if edge.isDegenerate:
                continue
            try:
                
                edgeObject = SelectedEdge(edge, self)
                logger.debug(' {} - edge object added'.format(edgeObject.edgeHash))
    
#                self.validEdges[edgeObject.edgeHash] = edgeObject
            except:
                dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))
                
    def __del__(self):
        print ("deleted face {}".format(self.faceHash))
        self.registeredFaces.remove(self.face)
#        self.parent.registeredComponents.remove(self.occurrenceName)
        del self.selectedFaces[self.faceHash]
        logger.debug(' {} - face key deleted from registeredFaces'.format(self.faceHash))
        for edgeObject in self.registeredEdges.values():
            del edgeObject
            logger.debug(' {} - edge object deleted'.format(edgeObject.edgeHash))
                
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
            if not len(self.selectedFaces): #if there are no selected Faces, remove all faceObjects with occurrence
                                            #- this cleans up registeredFaces and allows other faces/occurrences to be selectable
                self.registeredFaces.remove(self)
                del self.parent.registeredFaces[self.occurrenceName]
                logger.debug(' {} - face object removed from registeredFaces'.format(self.faceHash))
            self.selectedFaces.remove(self)
            logger.debug(' {} - face object removed from selectedFaces'.format(self.faceHash))
        else:
            self.selectedFaces.append(self)
            logger.debug(' {} - face object added to registeredFaces'.format(self.faceHash))

        for edge in self.registeredEdges:
            edge.selected = selected
            logger.debug(' {} - edge object selected - {}'.format(edge.edgeHash, selected))
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
