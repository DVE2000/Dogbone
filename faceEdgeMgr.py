# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 19:51:42 2019

@author: Peter Ludikar
"""

import logging
from pprint import pformat

from sys import getrefcount as grc

from collections import defaultdict, namedtuple
from math import pi, tan

import adsk.core, adsk.fusion
import traceback
import weakref
import json
from functools import reduce, lru_cache

from . import dbutils as dbUtils
from . import DbParams
from . import dbFaces
from math import sqrt, pi

#==============================================================================
# constants - to keep attribute group and names consistent
#==============================================================================
DBGROUP = 'dbGroup'
DBEDGE_REGISTERED = 'dbEdgeRegistered'
DBFACE_REGISTERED = 'dbFaceRegistered'
DBEDGE_SELECTED = 'dbEdgeSelected'
DBFACE_SELECTED = 'dbFaceSelected'
FACE_ID = 'faceID'
REV_ID = 'revId'
ID = 'id'
DEBUGLEVEL = logging.NOTSET

#==============================================================================
# Utility Functions
#==============================================================================
faceSelections = lambda selectionObjects: list(filter(lambda face: face.objectType == adsk.fusion.BRepFace.classType(), selectionObjects))
edgeSelections = lambda selectionObjects: list(filter(lambda edge: edge.objectType == adsk.fusion.BRepEdge.classType(), selectionObjects))

# Generate occurrence hash
calcOccHash = lambda x: x.assemblyContext.name if x.assemblyContext else x.body.name

# Generate an edgeHash or faceHash from object
calcHash = lambda x: str(x.tempId) + ':' + x.assemblyContext.name.split(':')[-1] if x.assemblyContext else str(x.tempId) + ':' + x.body.name

HashLoad = namedtuple('Hashload',['faceHash','occHash'])
EdgeParams = namedtuple('EdgeParams',['edgeHash','params'])

#==============================================================================
# Main class definition
#==============================================================================
class Groups:

    """ 
    The purpose of this object is to group together all related faces and associated edges in order to make finding and processing edges and faces inherently easy  

    It provides the means of initializing face/edge groups in a particular component or body (if a root body)

    Initializing with a face will result in complete identification of:
         the primary face
         all associated faces that are parallel to the primary face - aka registered faceObjects
         all viable associated dogbone edges - aka registered edgeObjects
         all selected faces that will contain one or more dogbone edges - aka selectedFaces
         all selected edges - aka selectedEdges

    This object provides basic collation and processing functions - so that face and edge Objects can remain behind the scenes to the outside
    It also holds the full list of registered and selected face and edge objects - drilling down to a face or edge will inherently only make the relevant entries 
    available to the face or edge objects

    """


    def __init__(self):
        self.logger = logging.getLogger('dogbone.mgr')
        
        self.logger.info('---------------------------------{}---------------------------'.format('faceEdgeMgr'))
        self.logger.debug('faceEdgeMgr initiated')
        self.dbGroups = {} #key groupHash value: dbGroupObject
        self.registeredFaces = {} #key: occurrenceHash value: dict of key: facehash value: faceObjects
        self.registeredEdges = {} #key: facehash value: dict of key:  edgehash value: edgeObjects
        self.topFacePlanes = {} #key: occurrenceHash value:topFace plane - NOTE: may be better relegated to dbGroup level
        self.selectedFaces = {} #key: occurrenceHash value: dict of key: facehash value: faceObjects
        self.selectedEdges = {} #key: facehash value: dict of key:  edgehash value: edgeObjects
        self.timeLineGroups = {} #key: occurrenceHash value: timelineGroup object - NOTE: may be better relegated to dbGroup level
        self.app = adsk.core.Application.get()
        self.design = self.app.activeProduct


    def addGroup(self, face):
        

            
    def clearAttribs(self, name):
        #not used - can be called manually during debugging
        attribs = self.design.findAttributes(name, '')
        for attrib in attribs:
            attrib.deleteMe()
            
    def preLoad(self):
        timelineGroups = self.design.timeline.timelineGroups
        try:
            dbTlGroups = list(filter(lambda x: 'db:' in x.name , timelineGroups))
        except:
            # timelineGroups is probably null
            return
        for tlGroup in dbTlGroups:
            tlgName = tlGroup.name
            occHash = tlgName[3:]
            tlGroup.isCollapsed = False
            featureBodyTLObject = tlGroup.item(0)
            featureBodyTLObject.isSuppressed = True
            self.timeLineGroups[occHash] = tlGroup
            self.registeredFaces[occHash] = {}
            bodyAttributes = self.design.findAttributes(DBGROUP, 'occId:'+occHash)
            for bodyAttribute in bodyAttributes:
                faceHashes = json.loads(bodyAttribute.value)
                for faceHash in faceHashes:
                    faceAttributes = self.design.findAttributes(DBGROUP, 'faceId:'+faceHash)
                    if not faceAttributes:
                        continue
                    for faceAttribute in faceAttributes:
                        if not faceAttribute.value:
                            continue
                        faceObject = SelectedFace(faceAttribute.parent, self, HashLoad(faceHash, occHash))

    def updateAttributes(self):
        #TODO
        for occHash, facesDict in self.registeredFaces.items():
            occHashFlag = True
            for faceObject in facesDict.values():
                if occHashFlag:
                    faceObject.face.body.attributes.add(DBGROUP, 'occId:'+occHash, json.dumps(list(faceObject.registeredFaces.keys())))
                    occHashFlag = False
                faceObject.refreshAttributes()
    
    @lru_cache(maxsize=128)
    def completeEntityList(self, entityHash):  #needs hashable parameters in the arguments for lru_cache to work
        self.logger.debug('Entity Hash  = {}'.format(entityHash))
        return  (entityHash in map(lambda x: x.faceHash, self.registeredFaceObjectsAsList)) or (entityHash in map(lambda x: x.edgeHash, self.registeredEdgeObjectsAsList))

    def isSelectable(self, entity):
        
        self._entity = entity

        if entity.assemblyContext:
            self.activeoccurrenceHash = entity.assemblyContext.component.name
        else:
            self.activeoccurrenceHash = entity.body.name
        if self.activeoccurrenceHash not in map(lambda x: x.split(":")[0], self.registeredFaces.keys()):
            return True

        return self.completeEntityList(calcHash(entity))
        
    @property        
    def registeredEdgeObjectsAsList(self):
        edgeList = []
        for comp in self.registeredEdges.values():
            edgeList += comp.values()
        return edgeList

    @property        
    def registeredFaceObjectsAsList(self):
        faceList = []
        for comp in self.registeredFaces.values():
            faceList += comp.values()
        return faceList
        
    @property
    def registeredEntitiesAsList(self):
        self.logger.debug('registeredEntitiesAsList')
        edgeList = []
        for comp in self.registeredEdges.values():
            edgeList += comp
        faceList = []
        for comp in self.registeredFaces.values():
            faceList += comp
            faceEntities = map(lambda faceObjects: faceObjects.face, edgeList)
            edgeEntities = map(lambda edgeObjects: edgeObjects.edge, faceList)
            return faceEntities + edgeEntities

    @property
    def selectedEdgeObjectsAsList(self):
        self.logger.debug('selectedEdgesAsList')
        edgeList = []
        for comp in self.selectedEdges.values():
            edgeList += comp.values()
        return edgeList    
        
    def selectedModeEdgeObjectsAsList(self, mode):
        self.logger.debug('selectedEdgesAsList')
        edgeList = []
        for comp in self.selectedEdges.values():
            if comp.mode != mode:
                continue
            edgeList += comp.values()
        return edgeList
            
    @property        
    def selectedFaceObjectsAsList(self):
        self.logger.debug('selectedFacesAsList')

        faceList = []
        for comp in self.selectedFaces.values():
            faceList += comp.values()
            
        #   x =  []+list(self.selectedFaces.values())
        #   edges = copy.deepcopy(self.selectedEdges)
        return faceList
                     
    @property        
    def selectedEdgesAsGroupList(self):  # Grouped by occurrence/component
        self.logger.debug('registeredEdgeObjectsAsGroupList')
        groupedEdges  = {}
        for occurrence in self.selectedFaces:
            edges = []
            for faceHash in self.selectedFaces[occurrence]:
                edges += self.selectedEdges[faceHash].values()
            groupedEdges[occurrence] = edges
        return groupedEdges



class Group:
    
    """ 
    Group is the associated group of faces and edges that have a common primary face, and common dogbone parameters - ie all edges that would be cut with the same dogbone 
    type and size in the same body or component.  It's also associated with a single timeline object (this is because dogbones could be created in any part of the
    timeline, and this app allows all dogbones to be edited at the same time - timeline will roll back to each appropriate group when edited.)
    """


    __init__(self, faceEntity, parent):
        self.logger = logging.getLogger('dogbone.mgr.dbGroup')

        self.logger.info('---------------------------------{}---------------------------'.format('creating group'))

        self.timeLineGroup

        self._dbParams = {}
        
        self.face = face # BrepFace
        self.faceNormal = dbUtils.getFaceNormal(self.face)
        
        self.faceHash = calcHash(face) if not preload else preload.faceHash


        self.tempId = face.tempId if not preload else preload.faceHash.split(':')[0]
        self._selected = True # record of all valid faces are kept, but only ones that are selected==True are processed for dogbones???
        self.registry = weakref.ref(parent)()

        self.groupHash = 
        self.groups = self.registry.groups.setdefault(self.groupHash,{} )

        self.occurrenceHash = calcOccHash(face) if not preload else preload.occHash
        self.topFacePlane = self.parent.topFacePlanes.setdefault(self.occurrenceHash, dbUtils.getTopFacePlane(face))
        
        self.registeredFaces = self.registry.registeredFaces.setdefault(self.occurrenceHash, {})
        self.registeredFaces[self.faceHash] = self
        self.registeredEdges = self.registry.registeredEdges.setdefault(self.faceHash, {})
        
        self.selectedFaces = self.registry.selectedFaces.setdefault(self.occurrenceHash, {})
        self.selectedEdges = self.registry.selectedEdges.setdefault(self.faceHash, {})
        self.logger.debug('{} - face initiated'.format(self.faceHash))       

    def addFace(self, face):
        #==============================================================================
        #         Adds face to registered and selected registries
        #==============================================================================
        self.logger.debug('registered Faces before = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces before = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges before = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges before = {}'.format(pformat(self.selectedEdges)))
            
        faces = self.selectedFaces.setdefault(calcOccHash(face), {})
        self.logger.debug('cache cleared')
        self.completeEntityList.cache_clear()

        if faces:
            faceObject = self.registeredFaces[calcOccHash(face)][calcHash(face)]
            faceObject.selected = True
            return
        
        body = face.body
        faceNormal = dbUtils.getFaceNormal(face)
        
        for face1 in body.faces:
            if faceNormal.angleTo(dbUtils.getFaceNormal(face1))== 0:
                faceObject = SelectedFace(face1, self)

        self.logger.debug('registered Faces after = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces after = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges after = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges after = {}'.format(pformat(self.selectedEdges)))
        
    def deleteFace(self, face):
        #TODO:
        self.logger.debug('registered Faces before = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces before = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges before = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges before = {}'.format(pformat(self.selectedEdges)))
        occHash = calcOccHash(face)
        face.attributes.itemByName(DBGROUP, DBFACE_REGISTERED).deleteMe()
        faceObject = self.registeredFaces[occHash][calcHash(face)]
        faceObject.selected = False
        if not self.selectedFaces[occHash]:
            self.remove(occHash)
        self.logger.debug('registered Faces after = {}'.format(pformat(self.registeredFaces)))
        self.logger.debug('selected Faces after = {}'.format(pformat(self.selectedFaces)))
        self.logger.debug('registered Edges after = {}'.format(pformat(self.registeredEdges)))
        self.logger.debug('selected Edges after = {}'.format(pformat(self.selectedEdges)))
        self.completeEntityList.cache_clear()
        self.logger.debug('cache cleared')

    def remove(self, occHash):
        for faceObject in self.registeredFaces[occHash].values():
            faceObject.face.attributes.itemByName(DBGROUP, DBFACE_REGISTERED).deleteMe()
            del self.registeredEdges[faceObject.faceHash]
            del self.selectedEdges[faceObject.faceHash]
        del self.registeredFaces[occHash]
        del self.selectedFaces[occHash]
        
    def addEdge(self, edge):
        edgeHash = calcHash(edge)
        for edgeList in self.registeredEdges.values():
            if calcHash(edge) in edgeList:
                edgeObject = edgeList[edgeHash]
                break
        self.logger.debug('cache cleared')
        self.completeEntityList.cache_clear()
        edgeObject.selected = True
        edgeObject.parent.selected = (True, False)
        
    def deleteEdge(self, edge):
        edgeHash = calcHash(edge)
        edge.attributes.itemByName(DBGROUP, DBEDGE_REGISTERED).deleteMe()
        for edgeList in self.registeredEdges.values():
            if calcHash(edge) in edgeList:
                edgeObject = edgeList[edgeHash]
                break
        edgeObject.selected = False
        if not edgeObject.selectedEdges:
            edgeObject.parent.selected = (False, False)
        if not edgeObject.parent.selectedFaces:
            self.remove(calcOccHash(edge))

