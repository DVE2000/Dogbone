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
from . import dbEdges
from math import sqrt, pi

class SelectedFace:
    """
    This class manages a single Face:
    keeps and makes a record of the viable edges, whether selected or not
    principle of operation: the first face added to a body/occurrence entity will find all other same facing faces, automatically finding eligible edges - they will all be selected by default.
    edges and faces have to be selected to be selected in the UI
    when all edges of a face have been deselected, the face becomes deselected
    when all faces of a body/entity have been deselected - the occurrence and all associated face and edge objects will be deleted and GC'd  (in theory)
    manages edges:
        edges can be selected or deselected individually
        faces can be selected or deselected individually
        first face selection will cause all other appropriate faces and corresponding edges on the body to be selected
        validEdges dict makes lists of candidate edges available
        each face or edge selection that is changed will reflect in the parent management object selectedOccurrences, selectedFaces and selectedEdges
    """

    def __init__(self, face, parent, preload = False):  #preload is used when faces are created from attributes.  preload will be a namedtuple of faceHash and occHash
        self.logger = logging.getLogger('dogbone.mgr.edge')

        self.logger.info('---------------------------------{}---------------------------'.format('creating face'))
        
        self.face = face # BrepFace
        self.faceNormal = dbUtils.getFaceNormal(self.face)
        
        self.faceHash = calcHash(face) if not preload else preload.faceHash


        self.tempId = face.tempId if not preload else preload.faceHash.split(':')[0]
        self._selected = True # record of all valid faces are kept, but only ones that are selected==True are processed for dogbones???
        self.group = weakref.ref(parent)()

        self.occurrenceHash = calcOccHash(face) if not preload else preload.occHash
        self.topFacePlane = self.group.topFacePlanes.setdefault(self.occurrenceHash, dbUtils.getTopFacePlane(face))
        
        self.registeredFaces = self.group.registeredFaces.setdefault(self.occurrenceHash, {})
        self.registeredFaces[self.faceHash] = self
        self.registeredEdges = self.group.registeredEdges.setdefault(self.faceHash, {})
        
        self.selectedFaces = self.group.selectedFaces.setdefault(self.occurrenceHash, {})
        self.selectedEdges = self.group.selectedEdges.setdefault(self.faceHash, {})
        self.logger.debug('{} - face initiated'.format(self.faceHash))           

        #==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        #==============================================================================
        
        if preload:
            faceAttribute = self.face.attributes.itemByName(DBGROUP, 'faceId:'+self.faceHash)
            edgeHashes = json.loads(faceAttribute.value)
            for edgeHash in edgeHashes:
                edgeAttributes = parent.design.findAttributes(DBGROUP, 'edgeId:'+edgeHash)
                self.selected = (True, False) if len(edgeAttributes)>0 else (False, False)
                for edgeAttribute in edgeAttributes:
                    edge = edgeAttribute.parent
                    edgeObject = SelectedEdge(edge, self, attributes = EdgeParams(edgeHash, edgeAttribute.value))
            return
            
        
        self.brepEdges = dbUtils.findInnerCorners(face) #get all candidate edges associated with this face
        if not self.brepEdges:
            self.logger.debug('no edges found on selected face '.format(self.faceHash))
            self._selected = False
            return

        self.logger.debug('{} - edges found on face creation'.format(len(self.brepEdges)))
        for edge in self.brepEdges:
            if edge.isDegenerate:
                continue
            try:
                
                edgeObject = SelectedEdge(edge, self)
                self.logger.debug(' {} - edge object added'.format(edgeObject.edgeHash))
    
            except:
                dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))
        self.selected = True
        self.logger.debug('registered component count = {}'.format(len(self.parent.registeredFaces.keys())))
                
    def __del__(self):
        self.logger.debug("face {} deleted".format(self.faceHash))
        del self.registeredFaces[self.faceHash]
        del self.selectedFaces[self.faceHash]
        self.logger.debug(' {} - face key deleted from registeredFaces'.format(self.faceHash))
        self.logger.debug('registered component count = {}'.format(len(self.parent.registeredFaces)))
        for edgeObject in self.registeredEdges.values():
            del edgeObject
            self.logger.debug(' {} - edge object deleted'.format(edgeObject.edgeHash))
        del self.parent.registeredEdges[self.faceHash]
        self.logger.debug('registered Faces count = {}'.format(len(self.registeredFaces)))               
        self.logger.debug('selected Faces count = {}'.format(len(self.selectedFaces)))               
        self.logger.debug('registered edges count = {}'.format(len(self.registeredEdges)))               
        self.logger.debug('selected edges count = {}'.format(len(self.selectededEdges)))
        
    def refreshAttributes(self):
        self.face.attributes.add(DBGROUP, 'faceId:'+self.faceHash, json.dumps(list(self.registeredEdges.keys())) if self.selected else '')
        for edgeObject in self.registeredEdges.values():
            edgeObject.refreshAttributes()

    def getAttributeValue(self):
        return self.face.attributes.itemByName(DBGROUP, 'faceId:'+self.occurrenceHash).value

    def setAttributeValue(self):
        
        self.face.attributes.add(DBGROUP, 'faceId:'+self.occurrenceHash, value)

    @property
    def selected(self):
        return self._selected
        
    @selected.setter
    def selected(self, selected):  #property setter only accepts a single argument - so multiple argments are passed via a tuple - which if exists, will carry allEdges and selected flags separately
        allEdges = True
        if isinstance(selected, tuple):
            allEdges = selected[1]
            selected = selected[0]
        self._selected = selected
        if not selected:
            del self.selectedFaces[self.faceHash]
            attr = self.face.attributes.itemByName(DBGROUP, DBFACE_SELECTED).deleteMe()

            self.logger.debug(' {} - face object removed from selectedFaces'.format(self.faceHash))
        else:
            self.selectedFaces[self.faceHash] = self
            #   attr = self.face.attributes.add(DBGROUP, DBFACE_SELECTED, dbType)
            self.logger.debug(' {} - face object added to registeredFaces'.format(self.faceHash))

        if allEdges:
            self.logger.debug('{} all edges after face {}'.format('Selecting' if selected else 'Deselecting', 'Selected' if selected else 'Deselected'))
            for edge in self.registeredEdges.values():
                try:
                    edge.selected = selected
                except:
                    continue
            self.logger.debug(' {} - edge object {}'.format(edge.edgeHash, 'selected' if selected else 'deselected'))
        self._selected = selected