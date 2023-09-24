import logging
import traceback
from math import tan, pi

import adsk.core
import adsk.fusion
from . import dbutils as dbUtils

logger = logging.getLogger("dogbone.DbClasses")

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = _app.activeProduct
_ui = _app.userInterface
_rootComp = _design.rootComponent


class DbFace:
    def __init__(
        self, parent, face: adsk.fusion.BRepFace, params, commandInputsEdgeSelect
    ):
        from .Dogbone import DogboneCommand

        self.face = face = (
            face if face.isValid else _design.findEntityByToken(self._entityToken)[0]
        )  # self.component.findBRepUsingPoint(self._refPoint, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)
        self.parent: DogboneCommand = parent
        self._entityToken = face.entityToken
        self._faceId = hash(self._entityToken)
        self.faceNormal = dbUtils.getFaceNormal(face)
        self._refPoint = (
            face.nativeObject.pointOnFace if face.assemblyContext else face.pointOnFace
        )
        self._component = face.body.parentComponent
        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self._selected = True
        self._params = params
        self._associatedEdgesDict = {}  # Keyed with edge
        processedEdges = (
            []
        )  # used for quick checking if an edge is already included (below)
        self._customGraphicGroup = None  #

        # ==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        # ==============================================================================

        faceNormal = dbUtils.getFaceNormal(face)

        faceEdgesSet = {hash(edge.entityToken) for edge in face.edges}
        faceVertices = [vertex for vertex in face.vertices]
        allEdges = {}
        for vertex in faceVertices:
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
                vector: adsk.core.Vector3D = dbUtils.getEdgeVector(edge, refFace=face)
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

                angle = dbUtils.getAngleBetweenFaces(edge) * 180 / pi
                if (
                    (abs(angle - 90) > 0.001)
                    and not (params.acuteAngle or params.obtuseAngle)
                    or (
                        not (params.minAngleLimit < angle <= 90)
                        and params.acuteAngle
                        and not params.obtuseAngle
                    )
                    or (
                        not (90 <= angle < params.maxAngleLimit)
                        and not params.acuteAngle
                        and params.obtuseAngle
                    )
                    or (
                        not (params.minAngleLimit < angle < params.maxAngleLimit)
                        and params.acuteAngle
                        and params.obtuseAngle
                    )
                ):
                    continue

                if (abs(angle - 90) > 0.001) and params.parametric:
                    continue

                edgeId = hash(edge.entityToken)
                parent.selectedEdges[edgeId] = self._associatedEdgesDict[
                    edgeId
                ] = DbEdge(edge=edge, parentFace=self)
                processedEdges.append(edge)
                parent.addingEdges = True
                self.commandInputsEdgeSelect.addSelection(edge)
                parent.addingEdges = False
            except:
                dbUtils.messageBox("Failed at edge:\n{}".format(traceback.format_exc()))

    def __hash__(self):
        return self.faceId

    def __del__(self):
        pass

    def __eq__(self, other):
        if type(other) != DbFace:
            return NotImplemented
        return other.faceId == self.faceId

    def selectAll(self):
        self._selected = True
        self.parent.addingEdges = True
        # selectedEdgesCollection = _ui.activeSelections.all
        # selectedEdgesDict = {hash(e.entityToken): e for e in selectedEdgesCollection if e.objectType == adsk.fusion.BRepEdge.classType()}
        [selectedEdge.select for selectedEdge in self._associatedEdgesDict.values()]
        # changedEdgeSelection = set(self._associatedEdgesDict.keys()) ^ set(selectedEdgesDict.keys())
        # updatedCollection = adsk.core.ObjectCollection.create()
        # [updatedCollection.add(self.parent.selectedEdges[e]) for e in changedEdgeSelection]
        # _ui.activeSelections.all = updatedCollection
        self.parent.addingEdges = False

    def deselectAll(self):
        self._selected = False
        self.parent.addingEdges = True
        [
            (
                selectedEdge.deselect,
                _ui.activeSelections.removeByEntity(selectedEdge.edge),
            )
            for selectedEdge in self._associatedEdgesDict.values()
        ]
        self.parent.addingEdges = False

    def reSelectEdges(self):
        # self._associatedEdgesDict = {}
        self.__init__(
            self.parent, self.face, self._params, self.commandInputsEdgeSelect
        )

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
        return [
            edgeObj
            for edgeObj in self._associatedEdgesDict.values()
            if edgeObj.isSelected
        ]

    def deleteEdges(self):
        [
            (
                _ui.activeSelections.removeByEntity(edgeObj.edge),
                self.parent.selectedEdges.pop(edgeId),
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
        return (
            self.face.assemblyContext.component
            if self.face.assemblyContext
            else _rootComp
        )

    @property
    def occurrence(self) -> adsk.fusion.Occurrence:
        return (
            self.face.assemblyContext if self.face.assemblyContext else self.face.body
        )

    @property
    def occurrenceId(self) -> adsk.fusion.Occurrence:
        return (
            hash(self.face.assemblyContext.entityToken)
            if self.face.assemblyContext
            else hash(self.face.body.entityToken)
        )

    def removeFaceFromSelectedOccurrences(self):
        faceList = self.parent.selectedOccurrences[self.occurrenceId]
        faceList.remove(self)

    @property
    def native(self):
        return self.face.nativeObject if self.face.nativeObject else self.face

    def revalidate(self) -> adsk.fusion.BRepFace:
        return self.component.findBRepUsingPoint(
            self._refPoint, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False
        ).item(0)


class DbEdge:
    def __init__(self, edge: adsk.fusion.BRepEdge, parentFace: DbFace):
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

        self._refPoint = (
            edge.nativeObject.pointOnEdge if edge.assemblyContext else edge.pointOnEdge
        )

        self._edgeId = hash(edge.entityToken)
        self._selected = True
        self._parentFace = parentFace
        self._native = self.edge.nativeObject if self.edge.nativeObject else self.edge
        self._component = edge.body.parentComponent

        face1, face2 = (face for face in self._native.faces)
        _, face1normal = face1.evaluator.getNormalAtPoint(face1.pointOnFace)
        _, face2normal = face2.evaluator.getNormalAtPoint(face2.pointOnFace)
        face1normal.add(face2normal)
        face1normal.normalize()
        self._cornerVector = face1normal

        self._cornerAngle = dbUtils.getAngleBetweenFaces(edge)
        self._customGraphicGroup = None

        self._dogboneCentre = (
            self.native.startVertex.geometry
            if self.native.startVertex in self._parentFace.native.vertices
            else self.native.endVertex.geometry
        )

        self._nativeEndPoints = (
            (self.native.startVertex.geometry, self.native.endVertex.geometry)
            if self.native.startVertex in self._parentFace.native.vertices
            else (self.native.endVertex.geometry, self.native.startVertex.geometry)
        )

        startPoint, endPoint = self._nativeEndPoints

        self._nativeEdgeVector: adsk.core.Vector3D = startPoint.vectorTo(endPoint)
        self._nativeEdgeVector.normalize()

        self._endPoints = (
            (self.edge.startVertex.geometry, self.edge.endVertex.geometry)
            if self.edge.startVertex in self._parentFace.face.vertices
            else (self.edge.endVertex.geometry, self.edge.startVertex.geometry)
        )

    def __hash__(self):
        return self._edgeId

    @property
    def select(self):
        self._selected = True

    @property
    def component(self) -> adsk.fusion.Component:
        return self._component
        # return self.edge.assemblyContext.component if self.edge.assemblyContext else _rootComp

    @property
    def cornerAngle(self):
        return self._cornerAngle

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
    def dogboneCentre(self) -> adsk.core.Point3D:
        """
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._dogboneCentre

    @property
    def nativeEndPoints(self) -> adsk.fusion.BRepVertex:
        """
        returns native Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._nativeEndPoints

    @property
    def endPoints(self) -> adsk.fusion.BRepVertex:
        """
        returns occurrence Edge Point associated with parent Face - initial centre of the dogbone
        """
        return self._endPoints

    @property
    def cornerEdges(self):
        return dbUtils.getCornerEdgesAtFace(face=self._parentFace, edge=self.edge)

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

    @property
    def native(self):
        return self.edge.nativeObject if self.edge.nativeObject else self.edge

    @classmethod
    def __getToolBody(cls, edgeObj, params, topFace: adsk.fusion.BRepFace = None):
        from .DbData import DbParams

        params: DbParams
        edgeObj: DbEdge

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
        startPoint, endPoint = edgeObj.nativeEndPoints
        startPoint, endPoint = startPoint.copy(), endPoint.copy()
        effectiveRadius = (params.toolDia + params.toolDiaOffset) / 2
        centreDistance = effectiveRadius * (
            (1 + params.minimalPercent / 100)
            if params.dbType == "Minimal Dogbone"
            else 1
        )

        if topFace:
            translateVector = dbUtils.getTranslateVectorBetweenFaces(
                edgeObj._parentFace.face, topFace
            )
            startPoint.translateBy(translateVector)

        if params.dbType == "Mortise Dogbone":
            (edge0, edge1) = edgeObj.cornerEdges
            direction0 = dbUtils.correctedEdgeVector(edge0, startPoint)
            direction1 = dbUtils.correctedEdgeVector(edge1, startPoint)
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
            dirVect = edgeObj.cornerVector.copy()
            dirVect.normalize()

        dirVect.scaleBy(centreDistance)
        startPoint.translateBy(dirVect)
        endPoint.translateBy(dirVect)

        toolbody = tempBrepMgr.createCylinderOrCone(
            endPoint, effectiveRadius, startPoint, effectiveRadius
        )

        if edgeObj.cornerAngle >= pi / 2:
            return toolbody

        # creating a box that will be used to clear the path the tool takes to the dogbone hole
        # box width is toolDia
        # box height is same as edge length
        # box length is from the hole centre to the point where the tool meets the sides

        edgeHeight = startPoint.distanceTo(endPoint)

        logger.debug("Adding acute angle clearance box")
        cornerTan = tan(edgeObj.cornerAngle / 2)

        boxCentrePoint = startPoint.copy()
        boxLength = effectiveRadius / cornerTan - centreDistance
        boxWidth = effectiveRadius * 2

        lengthDirectionVector = edgeObj.cornerVector.copy()
        lengthDirectionVector.normalize()
        lengthDirectionVector.scaleBy(boxLength / 2)

        if lengthDirectionVector.length < 0.01:
            return toolbody

        heightDirectionVector = edgeObj.edgeVector.copy()
        heightDirectionVector.normalize()
        heightDirectionVector.scaleBy(edgeHeight / 2)

        heightDirectionVector.add(lengthDirectionVector)

        lengthDirectionVector.normalize()

        boxCentrePoint.translateBy(heightDirectionVector)

        #   rotate centreLine Vector (cornerVector) by 90deg to get width direction vector
        orthogonalMatrix = adsk.core.Matrix3D.create()
        orthogonalMatrix.setToRotation(pi / 2, edgeObj.edgeVector, boxCentrePoint)

        widthDirectionVector = edgeObj.cornerVector.copy()
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

    def getToolBody(self, params, topFace: adsk.fusion.BRepFace = None):
        return DbEdge.__getToolBody(self, params, topFace)

    def addCustomGraphic(self):
        if not self._parentFace._customGraphicGroup:
            self._parentFace._customGraphicGroup = (
                self._component.customGraphicsGroups.add()
            )
        coordList = []
        [coordList.extend([n for n in p.asArray()]) for p in self.endPoints]
        coords = adsk.fusion.CustomGraphicsCoordinates.create(coordList)

        # body:adsk.fusion.CustomGraphicsBRepBody = self._parentFace._customGraphicGroup.addBRepBody(self.edge.body)

        line: adsk.fusion.CustomGraphicsLine = (
            self._parentFace._customGraphicGroup.addLines(coords, [], False)
        )
        line.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(0, 255, 0, 255)
        )
        line.id = str(self._edgeId)
        line.isSelectable = True
