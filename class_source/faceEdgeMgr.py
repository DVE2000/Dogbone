# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 19:51:42 2019

@author: Peter Ludikar
"""

import logging
from pprint import pformat
import adsk.core, adsk.fusion

from sys import getrefcount as grc

from collections import defaultdict, namedtuple
from math import pi, tan

# import adsk.core, adsk.fusion
import traceback
import weakref
import json
from functools import reduce, lru_cache
import hashlib

from common import dbutils as dbUtils
from common import dbParamsClass
from common.dbutils import calcOccHash, calcHash 
from class_source.dbFaces import DbFaces, DbFace
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

HashLoad = namedtuple('Hashload',['faceHash','occHash'])
EdgeParams = namedtuple('EdgeParams',['edgeHash','params'])

#==============================================================================
# Main class definition
#==============================================================================
class DbGroups:

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
    It also holds the full list of registered and selected face and edge objects - drilling down to a face or edge will inherently only make the
    relevant entries available to the face or edge objects

    """


    def __init__(self):
        self.logger = logging.getLogger('dogbone.mgr')
        
        self.logger.info('---------------------------------{}---------------------------'.format('faceEdgeMgr'))
        self.logger.debug('dbGroups initiated')
        self.dbOccurrences = set() #value: body or component name - to keep track of which body or component has dogbones
        self.dbGroups = set() #value: dbGroupObject
        self.dbFaces = set() #values: dbFaceObjects
        self.dbEdges =  set() #values: dbEdgeObjects
 
        self.app = adsk.core.Application.get()
        self.design = self.app.activeProduct

    def __iter__(self):
        for group in self.dbGroups:
            yield group

    def addFace(self, face, dbParams):
        self.dbGroups.add(DbGroup(face, self, dbParams))
            
    def clearAttribs(self, name):
        #not used - can be called manually during debugging
        attribs = self.design.findAttributes(name, '')
        for attrib in attribs:
            attrib.deleteMe()
            
    def preLoad(self):
        pass
    
    """     timelineGroups = self.design.timeline.timelineGroups
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
"""    
    @lru_cache(maxsize=128)
    def completeEntityList(self, entityHash):  #needs hashable parameters in the arguments for lru_cache to work
        self.logger.debug('Entity Hash  = {}'.format(entityHash))
        return  entityHash in self.dbEdges or entityHash in self.dbFaces

    def isSelectable(self, entity):
        
        activeoccurrenceHash = entity.assemblyContext.component.name if entity.assemblyContext else entity.body.name
        if activeoccurrenceHash not in self.dbOccurrences:
            return True

        return self.completeEntityList(hash(calcHash(entity)))
        
    @property        
    def registeredEdgeObjectsAsList(self):
        return self.dbEdges

    @property        
    def registeredFaceObjectsAsList(self):
        return self.dbFaces
        
    @property
    def registeredEntitiesAsList(self):
        self.logger.debug('registeredEntitiesAsList')
        return self.dbFaces + self.dbEdges

    @property
    def selectedEdgeObjectsAsList(self):
        self.logger.debug('selectedEdgesAsList')
        return [edgeObject for edgeObject in self.dbEdges if edgeObject.selected]    
            
    @property        
    def selectedFaceObjectsAsList(self):
        self.logger.debug('selectedFacesAsList')
        return [ faceObject for faceObject in self.dbFaces if faceObject.selected]
                     
    @property        
    def selectedEdgesAsGroupList(self):  # Grouped by occurrence/component
        self.logger.debug('registeredEdgeObjectsAsGroupList')
        groupedEdges  = {}
        for group in self.dbGroups:
            groupedEdges[group] = [edge.edge for edge in self.dbEdges if edge.group == group and edge.selected]
        return groupedEdges

    @property
    def registeredOccurrencesAsList(self):
        return self.dbOccurrences

class DbGroup:
    
    """ 
    Group is the associated group of dogbone faces and edges that have a common primary face, and common dogbone parameters - ie all edges that would be cut with the same dogbone 
    type and size in the same body or component.  It's also associated with a single timeline object (this is because dogbones could be created in any part of the
    timeline, and this app allows all dogbones to be edited at the same time - timeline will roll back to each appropriate group when edited.)
    """

    def __init__(self, faceEntity, parent, dbParams):
        self.logger = logging.getLogger('dogbone.mgr.dbGroup')

        self.groups = weakref.ref(parent)()
        self.dbFaces = self.groups.dbFaces
        self.dbEdges = self.groups.dbEdges
        self.groups.dbOccurrences.add(calcOccHash(faceEntity))

        self.logger.info('---------------------------------{}---------------------------'.format('creating group'))

        self.timeLineGroup = []

        self._dbParams = dbParams
        
        self.faceNormal = dbUtils.getFaceNormal(faceEntity)
        
        self.topFacePlane = dbUtils.getTopFacePlane(faceEntity)
        self.groupHash = hash((calcOccHash(topFacePlane), self._dbParams.idTuple))
                
        self.logger.debug('{} - group initiated'.format((calcOccHash(self.topFacePlane), self._dbParams.idTuple)))    

    def __hash__(self):
        return self.groupHash

    def addFaces(self, face):

        body = face.body
        faceNormal = dbUtils.getFaceNormal(face)
        
        for face1 in body.faces:
            if faceNormal.angleTo(dbUtils.getFaceNormal(face1))== 0:
                faceObject = self.addFace(face1, self)


    def addFace(self, face, parentFaces):
        #==============================================================================
        #         Adds face to registered and selected registries
        #==============================================================================
        self.logger.debug('registered Faces before = {}'.format(pformat(self.dbFaces)))
        self.logger.debug('registered Edges before = {}'.format(pformat(self.dbEdges)))
            
        faces = self.selectedFaces.setdefault(calcOccHash(face), {})
        self.logger.debug('cache cleared')
        self.completeEntityList.cache_clear()

        if faces:
            faceObject = self.registeredFaces[calcOccHash(face)][calcHash(face)]
            faceObject.selected = True
            return
        
        self.logger.debug('registered Faces after = {}'.format(pformat(self.dbFaces)))
        self.logger.debug('registered Edges after = {}'.format(pformat(self.dbEdges)))
        
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

