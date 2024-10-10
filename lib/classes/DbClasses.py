"""Main dogbone classes - Face Entities, Edge Entities and class for keeping a register of entities that have been selected"""
import logging
import traceback
from math import tan, pi
import json
from typing import cast, Dict, List

import adsk.core
import adsk.fusion

from .DbData import DbParams
from ..common.errors import FaceInvalidError, EdgeInvalidError
from ...constants import DB_GROUP
from ..utils import getFaceNormal, getEdgeVector, getAngleBetweenFaces, messageBox, getCornerEdgesAtFace, getTranslateVectorBetweenFaces, correctedEdgeVector
# logger = logging.getLogger("dogbone.DbClasses")

class Selection:
    def __init__(self) -> None:

        self.addingEdges: bool = False

        self.selectedOccurrences = {}  # key hash(occurrence.entityToken) value:[DbFace,...]
        self.selectedFaces: Dict[int, "DbFace"] = {}
        self.selectedEdges: Dict[int, "DbEdge"] = {}

        self.edges: List[adsk.fusion.BRepEdge] = []
        self.faces: List[adsk.fusion.BRepFace] = []


class DbFace:
    logger = logging.getLogger("dogbone.DbFace")

    def __init__(
            self,
            face: adsk.fusion.BRepFace,
            selection: Selection = Selection(),
            params: DbParams=DbParams(),
            commandInputsEdgeSelect = None,
            restoreState = False
    ):
        app = adsk.core.Application.get()
        design: adsk.fusion.Design = app.activeProduct
        self.rootComp = design.rootComponent
        self.ui = app.userInterface

        self._params = params
        self.selection = selection
        self._entityToken = face.entityToken

        self.face = face = (
            face if face.isValid else design.findEntityByToken(self._entityToken)[0]
        )

        self._faceId = hash(self._entityToken)
        DbFace.logger.debug(f'FaceCreated: {self._faceId}')
        self.faceNormal = getFaceNormal(face)
        self._refPoint = (
            face.nativeObject.pointOnFace if face.nativeObject else face.pointOnFace
        )
        self._component = face.body.parentComponent
        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self._selected = True
        self._body = self.face.body.nativeObject if self.face.nativeObject else self.face.body

        self._associatedEdgesDict = {}  # Keyed with edge
        self.processedEdges = (
            []
        )  # used for quick checking if an edge is already included (below)
        self._customGraphicGroup = None  #

        self._restoreState = restoreState

        if self._restoreState:
            self.restore()

        self.registerEdges()

    def registerEdges(self):
        # ==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        # ==============================================================================

        faceEdgesSet = {hash(edge.entityToken) for edge in self.face.edges}
        faceVertices = [vertex for vertex in self.face.vertices]
        allEdges = {}  #dict key:hash(entity code): BrepEdge

        #populate allEdges dict with all edges associated with face vertices
        for vertex in faceVertices:
            allEdges.update({hash(edge.entityToken): edge for edge in vertex.edges})

        candidateEdgesId = set(allEdges.keys()) - faceEdgesSet  #remove edges associated with face - just leaves corner edges
        candidateEdges = [allEdges[edgeId] for edgeId in candidateEdgesId] #create list of corner edges

        for edge in candidateEdges:
            if not edge.isValid:
                continue
            if edge.isDegenerate:
                continue
            if edge in self.processedEdges:
                continue
            try:
                if edge.geometry.curveType != adsk.core.Curve3DTypes.Line3DCurveType:
                    continue # make sure corner edge is only a straight line
                vector: adsk.core.Vector3D = getEdgeVector(edge, refFace=self.face)
                vector.normalize()
                if not vector.isParallelTo(self.faceNormal):
                    continue  #make sure corner edge is perpendicular to top face
                if vector.isEqualTo(self.faceNormal):
                    continue #make sure corner edge is down (face normals are always pointing out of body )
                
                #make sure faces adjoining corner edge are planes
                face1, face2 = edge.faces
                if face1.geometry.objectType != adsk.core.Plane.classType():
                    continue
                if face2.geometry.objectType != adsk.core.Plane.classType():
                    continue

                angle = round(getAngleBetweenFaces(edge) * 180 / pi, 3)
                if (
                    (abs(angle - 90) > 0.001)
                    and not (self._params.acuteAngle or self._params.obtuseAngle)
                    ):  
                    continue #Angle outside tolerance and we're just doing 90 corners

                if (
                        not (self._params.minAngleLimit < angle <= 90)
                        and self._params.acuteAngle
                        and not self._params.obtuseAngle
                    ):
                    continue  #angle less than lowest limit and doing acute angles

                if (
                        not (90 <= angle < self._params.maxAngleLimit)
                        and not self._params.acuteAngle
                        and self._params.obtuseAngle
                    ):
                    continue # angle greater than max limit and doing obtuse angles

                if (
                        not (self._params.minAngleLimit < angle < self._params.maxAngleLimit)
                        and self._params.acuteAngle
                        and self._params.obtuseAngle
                    ):
                    continue #angle between min and max and doing both acute and obtuse

                edgeId = hash(edge.entityToken) #this normally created by the DbEdge instantiation, but it's needed earlier (I thmk!)
                self.selection.selectedEdges[edgeId] = self._associatedEdgesDict[ 
                    edgeId
                ] = DbEdge(edge=edge, parentFace=self)
                self.processedEdges.append(edge)
                self.selection.addingEdges = True
                if not self._restoreState:
                    self.commandInputsEdgeSelect.addSelection(edge)
                self.selection.addingEdges = False

            except EdgeInvalidError:
                continue

            except Exception as e:
                DbFace.logger.exception(e)
                messageBox("Failed at edge:\n{}".format(traceback.format_exc()))

    def __hash__(self):
        return self.faceId

    def __del__(self):
        pass

    def __eq__(self, other):
        if type(other) != DbFace:
            return NotImplemented
        return other.faceId == self.faceId
    

    def save(self):
        """
        Saves parameters and state to edge attribute 
        """
        params = self._params.to_dict()
        params.update({"selected":self._selected})
        self.face.attributes.add(DB_GROUP, "face:"+str(self._faceId), json.dumps(params))
        self.face.attributes.add(DB_GROUP, "token:", self._entityToken)

    def restore(self):
        """
        restores face parameters and state from attribute 
        """
        if not( attr := self.face.attributes.itemByName(DB_GROUP, "face:"+str(self._faceId))):
            try:
                attr = [att for att in self.face.attributes if 'face:' in att.name ][0]
            except:
                raise FaceInvalidError
            
        value = attr.value
        params = json.loads(value)
        self._selected = params.pop("selected")
        self._params = DbParams(**params)

    def selectAll(self):
        """
        Marks all registered Edges as selected
        """
        self._selected = True
        self.selection.addingEdges = True
        [selectedEdge.select() for selectedEdge in self._associatedEdgesDict.values()]
        self.selection.addingEdges = False

    def deselectAll(self):
        """
        Marks all registered Edges as deselected
        """
        self._selected = False
        self.selection.addingEdges = True
        [
            (
                selectedEdge.deselect(),
                self.ui.activeSelections.removeByEntity(selectedEdge.edge),
            )
            for selectedEdge in self._associatedEdgesDict.values()
        ]
        self.selection.addingEdges = False

    def reSelectEdges(self):
        self.__init__(
            face = self.face,
            selection = self.selection,  
            params = self._params, 
            commandInputsEdgeSelect = self.commandInputsEdgeSelect
        )

    @property
    def entityToken(self):
        return self._entityToken

    @property
    def refPoint(self):
        return self._refPoint

    def select(self):
        self._selected = True

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
        return [
            edgeObj
            for edgeObj in self._associatedEdgesDict.values()
            if edgeObj.isSelected
        ]
    
    @property
    def body(self):
        return self._body
    
    @property
    def vertices(self):
        return [vertex for vertex in self.face.vertices]

    def deleteEdges(self):
        [
            (
                self.ui.activeSelections.removeByEntity(edgeObj.edge),
                self.selection.selectedEdges.pop(edgeId),
            )
            for edgeId, edgeObj in self._associatedEdgesDict.items()
        ]
        try:
            del self._associatedEdgesDict
        except AttributeError:
            return

    @property
    def faceId(self):
        return self._faceId

    @property
    def component(self) -> adsk.fusion.Component:
        """
        Returns component associated with this face, or rootComp if not in assemblyContext
        """
        return (
            self.face.assemblyContext.component
            if self.face.assemblyContext
            else self.rootComp
        )

    @property
    def occurrence(self) -> adsk.fusion.Occurrence:
        return (
            self.face.assemblyContext if self.face.assemblyContext else self.face.body
        )

    @property
    def occurrenceId(self) -> int:
        return (
            hash(self.face.assemblyContext.entityToken)
            if self.face.assemblyContext
            else hash(self.face.body.entityToken)
        )

    def removeFaceFromSelectedOccurrences(self):
        faceList = self.selection.selectedOccurrences[self.occurrenceId]
        faceList.remove(self)

    @property
    def native(self):
        return self.face.nativeObject if self.face.nativeObject else self.face

    def revalidate(self) -> adsk.fusion.BRepFace:
        return cast(adsk.fusion.BRepFace, self.component.findBRepUsingPoint(
            self._refPoint, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False
        ).item(0))


class DbEdge:
    logger = logging.getLogger("dogbone.DbEdge")

    def __init__(self, edge: adsk.fusion.BRepEdge, parentFace: DbFace):


        self._refPoint = (
            edge.nativeObject.pointOnEdge if edge.nativeObject else edge.pointOnEdge
        )

        self.edge = edge = (
            edge
            if edge.isValid
            else self.component.findBRepUsingPoint(
                self._refPoint,
                adsk.fusion.BRepEntityTypes.BRepEdgeEntityType,
                -1.0,
                False,
            ).item(0)
        )

        self.entityToken = edge.entityToken
        self._edgeId = hash(self.entityToken)
        self._selected = True
        self._parentFace = parentFace
        self._native = self.edge.nativeObject if self.edge.nativeObject else self.edge
        self._component = edge.body.parentComponent
        self._params = self._parentFace._params

        face1, face2 = (face for face in self._native.faces)
        _, face1normal = face1.evaluator.getNormalAtPoint(face1.pointOnFace)
        _, face2normal = face2.evaluator.getNormalAtPoint(face2.pointOnFace)
        face1normal.add(face2normal)
        face1normal.normalize()
        self._cornerVector = face1normal

        self._cornerAngle = getAngleBetweenFaces(edge)
        self._customGraphicGroup = None

        self._dogboneCentre = (
            self._native.startVertex.geometry
            if self._native.startVertex in self._parentFace.native.vertices
            else self._native.endVertex.geometry
        )

        self._nativeEndPoints = (
            (self._native.startVertex.geometry, self._native.endVertex.geometry)
            if self._native.startVertex in self._parentFace.native.vertices
            else (self._native.endVertex.geometry, self._native.startVertex.geometry)
        )

        startPoint, endPoint = self._nativeEndPoints

        self._nativeEdgeVector: adsk.core.Vector3D = startPoint.vectorTo(endPoint)
        self._nativeEdgeVector.normalize()

        self._endPoints = (
            (self.edge.startVertex.geometry, self.edge.endVertex.geometry)
            if self.edge.startVertex in self._parentFace.face.vertices
            else (self.edge.endVertex.geometry, self.edge.startVertex.geometry)
        )

        sx,sy,sz = self._nativeEndPoints[0].asArray()
        ex,ey,ez = self._nativeEndPoints[1].asArray()

        DbEdge.logger.debug(f'\nedge: {self.edge.tempId}'
                    f'\n native: {self.edge.nativeObject != None}'
                    f'\n startPoint: ({sx:.2f},{sy:.2f},{sz:.2f}),({ex:.2f},{ey:.2f},{ez:.2f})'
                    f'\n edgeLength: {startPoint.distanceTo(endPoint):.2f}'
                    f'\n parentFace: {self._parentFace.face.tempId}')
        
        if self._parentFace._restoreState:
            self.restore()

    def __hash__(self):
        return self._edgeId

    def select(self):
        self._selected = True

    def save(self):
        """
        Saves parameters and state to edge attribute 
        """
        params = self._params.to_dict()
        params.update({"selected":self._selected})
        self.edge.attributes.add(DB_GROUP, "params:", json.dumps(params))

    def restore(self):
        """
        restores edge parameters and state from attribute 
        """
        if not(attr := self.edge.attributes.itemByName(DB_GROUP, "params:")):
            self._selected = True
            self.save()
            return
            # raise EdgeInvalidError
        value = attr.value
        params = json.loads(value)
        self._selected = params.pop("selected")
        self._params = DbParams(**params)
        
    @property
    def component(self) -> adsk.fusion.Component:
        return self._component

    @property
    def cornerAngle(self):
        return self._cornerAngle

    def deselect(self):
        self._selected = False

    @property
    def isSelected(self):
        return self._selected

    @property
    def native(self):
        return self._native

    @property
    def dogboneCentre(self) -> adsk.core.Point3D:
        """
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._dogboneCentre

    @property
    def nativeEndPoints(self) -> tuple[adsk.core.Point3D, adsk.core.Point3D]:
        """
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._nativeEndPoints

    @property
    def endPoints(self) -> tuple[adsk.core.Point3D, adsk.core.Point3D]:
        """
        returns occurrence Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._endPoints

    @property
    def cornerEdges(self):
        """
        returns the two face edges associated with dogbone edge that is orthogonal to the face edges 
        """
        return getCornerEdgesAtFace(face=self._parentFace, edge=self.edge)

    @property
    def cornerVector(self) -> adsk.core.Vector3D:
        """
        returns normalised vector away from the faceVertex that
        the dogbone needs to be located on
        """
        return self._cornerVector

    @property
    def edgeVector(self) -> adsk.core.Vector3D:
        """
        returns normalised vector away from the faceVertex that
        the dogbone needs to be located on
        """
        return self._nativeEdgeVector
    
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

    @classmethod
    def __getToolBody(cls,
                      self,
                      topFace: adsk.fusion.BRepFace = None):

        box = None
        topFace = topFace if topFace else getTopFace(self._parentFace.face)

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
        startPoint, endPoint = self.nativeEndPoints
        startPoint, endPoint = startPoint.copy(), endPoint.copy()

        sx,sy,sz = self._nativeEndPoints[0].asArray()
        ex,ey,ez = self._nativeEndPoints[1].asArray()
        params = self._params

        DbEdge.logger.debug(f'\nGet Tool Body:++++++++++++++++'
                f'\n native: {self.edge.nativeObject != None}'
                f'\n edge: {self.edge.tempId}'
                f'\n startPoint: ({sx:.2f},{sy:.2f},{sz:.2f}),({ex:.2f},{ey:.2f},{ez:.2f})'
                f'\n edgeLength: {startPoint.distanceTo(endPoint): .2f}')
                # f'\n parentFace: {self._parentFace.face.tempId}')
        
        effectiveRadius = (params.toolDia + params.toolDiaOffset) / 2
        centreDistance = effectiveRadius * (
            (1 + params.minimalPercent / 100)
            if params.dbType == "Minimal Dogbone"
            else 1
        )

        if topFace:
            translateVector = getTranslateVectorBetweenFaces(
                self._parentFace.native, topFace
            )
            startPoint.translateBy(translateVector)

        if params.dbType == "Mortise Dogbone":
            (edge0, edge1) = self.cornerEdges
            direction0 = correctedEdgeVector(edge0.nativeObject, startPoint)
            direction1 = correctedEdgeVector(edge1.nativeObject, startPoint)
            if params.longSide:
                if edge0.length > edge1.length:
                    dirVect = direction0
                else:
                    dirVect = direction1
            else:
                if edge0.length > edge1.length:
                    dirVect = direction1
                else:
                    dirVect = direction0
            dirVect.normalize()
        else:
            dirVect = self.cornerVector.copy()
            dirVect.normalize()

        dirVect.scaleBy(centreDistance)
        startPoint.translateBy(dirVect)
        endPoint.translateBy(dirVect)

        toolbody = tempBrepMgr.createCylinderOrCone(
            endPoint, effectiveRadius, startPoint, effectiveRadius
        )

        if self.cornerAngle >= pi / 2:
            return toolbody

        # creating a box that will be used to clear the path the tool takes to the dogbone hole
        # box width is toolDia
        # box height is same as edge length
        # box length is from the hole centre to the point where the tool meets the sides

        edgeHeight = startPoint.distanceTo(endPoint)

        DbEdge.logger.debug("Adding acute angle clearance box")
        cornerTan = tan(self.cornerAngle / 2)

        boxCentrePoint = startPoint.copy()
        boxLength = effectiveRadius / cornerTan - centreDistance
        boxWidth = effectiveRadius * 2

        lengthDirectionVector = self.cornerVector.copy()
        lengthDirectionVector.normalize()
        lengthDirectionVector.scaleBy(boxLength / 2)

        if lengthDirectionVector.length < 0.01:
            return toolbody

        heightDirectionVector = self.edgeVector.copy()
        heightDirectionVector.normalize()
        heightDirectionVector.scaleBy(edgeHeight / 2)

        heightDirectionVector.add(lengthDirectionVector)

        lengthDirectionVector.normalize()

        boxCentrePoint.translateBy(heightDirectionVector)

        #   rotate centreLine Vector (cornerVector) by 90deg to get width direction vector
        orthogonalMatrix = adsk.core.Matrix3D.create()
        orthogonalMatrix.setToRotation(pi / 2, self.edgeVector, boxCentrePoint)

        widthDirectionVector = self.cornerVector.copy()
        widthDirectionVector.transformBy(orthogonalMatrix)

        boxLength = 0.001 if (boxLength < 0.001) else boxLength

        boundaryBox = adsk.core.OrientedBoundingBox3D.create(
            centerPoint=boxCentrePoint,
            lengthDirection=lengthDirectionVector,
            widthDirection=widthDirectionVector,
            length=boxLength,
            width=boxWidth,
            height=edgeHeight,
        )

        box = tempBrepMgr.createBox(boundaryBox)

        tempBrepMgr.booleanOperation(
            targetBody=toolbody,
            toolBody=box,
            booleanType=adsk.fusion.BooleanTypes.UnionBooleanType,
        )

        return toolbody

    def getToolBody(self, topFace: adsk.fusion.BRepFace = None):
        return DbEdge.__getToolBody(self, topFace)

    def addCustomGraphic(self):
        if not self._parentFace._customGraphicGroup:
            self._parentFace._customGraphicGroup = (
                self._component.customGraphicsGroups.add()
            )
        coordList = []
        [coordList.extend([n for n in p.asArray()]) for p in self.endPoints]
        coords = adsk.fusion.CustomGraphicsCoordinates.create(coordList)

        line: adsk.fusion.CustomGraphicsLine = (
            self._parentFace._customGraphicGroup.addLines(coords, [], False)
        )
        line.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(0, 255, 0, 255)
        )
        line.id = str(self._edgeId)
        line.isSelectable = True
