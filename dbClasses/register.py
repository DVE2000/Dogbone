from functools import reduce, lru_cache
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List, ClassVar, Type
import adsk

class Register:

    registerList: List = []

    # def __init__(self, object: Type):
    #     print(object)
    #     if not isinstance(object, FaceRegister) and not isinstance(object, EdgeRegister):
    #         raise TypeError
        # Register.registerList.append(object)

    # @property
    # @classmethod
    # @abstractmethod
    # def register(cls)->List:
    #     return cls.registerList

    @lru_cache(maxsize=128)
    def completeEntityList(self, entityHash):  #needs hashable parameters in the arguments for lru_cache to work
        self.logger.debug('Entity Hash  = {}'.format(entityHash))
        return  entityHash in self.dbEdges or entityHash in self.dbFaces

    def isSelectable(self, entity):
        
        activeoccurrenceHash = entity.assemblyContext.component.name if entity.assemblyContext else entity.body.name
        if activeoccurrenceHash not in self.dbOccurrences:
            return True

        return self.completeEntityList(hash(entity.entityToken))
        
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

@dataclass(init=False)
class FaceObject:
    def __init__(self,faceEntity: adsk.fusion.BRepFace):
        Register.registerList.append(self)

@dataclass(init=False)
class EdgeObject:
    def __init__(self,edgeEntity: adsk.fusion.BRepEdge):
        Register.registerList.append(self)
