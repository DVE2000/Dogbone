import logging
import math

import adsk.core
import adsk.fusion

logger = logging.getLogger("dogbone.dbutils")


def getAngleBetweenFaces(edge: adsk.fusion.BRepEdge) -> float:
    """
    returns radian angle between faces
    """

    """
    Steps:
    get both adjacent faces of the edge
    crossProduct of these face Normals will point up or down
    to determine which is up compare direction with edge
    but: the edge direction needs to be determined 
    outer coEdges always run counterClockwise
    get the coEdge for face1
    orient the edge vector so it is has the same direction as the coEdge.
    
    Then with edge vertical, face1 on left, face2 on right, coEdge1 will be up
    if inside corner: face1normal x face2normal result will be in DOWN direction
    ie opposite to face1 coEdge direction
    """
    # Verify that the two faces are planar.
    face1, face2 = (face for face in edge.faces)
    if not face1 or not face2:
        return 0
    if (
        face1.geometry.objectType != adsk.core.Plane.classType()
        or face2.geometry.objectType != adsk.core.Plane.classType()
    ):
        return 0

    # Get the normal of each face.
    _, normal1 = face1.evaluator.getNormalAtPoint(face1.pointOnFace)
    _, normal2 = face2.evaluator.getNormalAtPoint(face2.pointOnFace)
    # Get the angle between the normals.
    normalAngle = normal1.angleTo(normal2)

    # Get the co-edge of the selected edge for face1.
    coEdge1, coEdge2 = (coEdge for coEdge in edge.coEdges)
    coEdge = coEdge1 if coEdge1.loop.face == face1 else coEdge2

    # Create a vector that represents the direction of the co-edge.
    edgeVec = getEdgeVector(edge, reverse=coEdge.isOpposedToEdge)

    # Get the cross product of the face normals.
    # normal1 and normal2 are flipped as edge vector is pointing "up"
    cross = normal2.crossProduct(normal1)

    # Check to see if the cross product is in the same or opposite direction
    # of the co-edge direction.  If it's opposed then it's a convex angle.
    angle = (
        (math.pi * 2) - (math.pi - normalAngle)
        if edgeVec.angleTo(cross) > math.pi / 2
        else math.pi - normalAngle
    )

    return angle


def findExtent(face: adsk.fusion.BRepFace, edge: adsk.fusion.BRepEdge):
    if edge.startVertex in face.vertices:
        return edge.endVertex

    return edge.startVertex


# TODO: startPoint and endPoint seems to be not properties of edge
def correctedEdgeVector(
    edge: adsk.fusion.BRepEdge, refPoint: adsk.core.Point3D
) -> adsk.core.Vector3D:
    if edge.startVertex.geometry.isEqualTo(refPoint):
        return edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
    return edge.endVertex.geometry.vectorTo(edge.startVertex.geometry)


def correctedSketchEdgeVector(edge, refPoint):
    if edge.startSketchPoint.geometry.isEqualTo(refPoint.geometry):
        return edge.startSketchPoint.geometry.vectorTo(edge.endSketchPoint.geometry)
    return edge.endSketchPoint.geometry.vectorTo(edge.startSketchPoint.geometry)


def isEdgeAssociatedWithFace(face: adsk.fusion.BRepFace, edge: adsk.fusion.BRepEdge) -> bool:
    # have to check both ends - not sure which way around the start and end vertices are
    if edge.startVertex in face.vertices:
        return True
    if edge.endVertex in face.vertices:
        return True
    return False


def getCornerEdgesAtFace(face: adsk.fusion.BRepFace, edge: adsk.fusion.BRepEdge):
    """
    Gets 
    """
    # not sure which end is which - so test edge ends for inclusion in face
    startVertex = (
        edge.startVertex if edge.startVertex in face.vertices else edge.endVertex
    )
    # edge has 2 adjacent faces - therefore the face that isn't from the 3 faces of startVertex, has to be the top face edges

    vertexEdges = {hash(edge.entityToken): edge for edge in startVertex.edges}
    faceEdges = {hash(edge.entityToken): edge for edge in face.face.edges}
    commonEdges = set(vertexEdges.keys()) & set(faceEdges.keys())  # intersect both sets
    if len(commonEdges) != 2:
        raise NameError("returnVal len != 2")
    return (faceEdges[token] for token in commonEdges)


def getVertexAtFace(face: adsk.fusion.BRepFace, edge: adsk.fusion.BRepEdge):
    if edge.startVertex in face.vertices:
        return edge.startVertex
    else:
        return edge.endVertex


def getEdgeVector(
    edge: adsk.fusion.BRepEdge, refFace: adsk.fusion.BRepFace = None, reverse=False
) -> adsk.core.Vector3D:
    """
    returns vector of the edge paramater (not normalised!)
    if refFace is supplied - returns vector pointing out from face vertex"""
    if refFace:
        reverse = edge.endVertex in refFace.vertices
    startPoint, endPoint = (
        (edge.endVertex.geometry, edge.startVertex.geometry)
        if reverse
        else (edge.startVertex.geometry, edge.endVertex.geometry)
    )
    return startPoint.vectorTo(endPoint)


def getFaceNormal(face: adsk.fusion.BRepFace):
    return face.evaluator.getNormalAtPoint(face.pointOnFace)[1]


def messageBox(*args):
    adsk.core.Application.get().userInterface.messageBox(*args)


def getTopFace(selectedFace: adsk.fusion.BRepFace) -> [adsk.fusion.BRepFace, adsk.core.Point3D]:
    """
    Returns the top-most face of a body and a Point3D reference point on that face, based on the supplied BrepFace 
    """
    normal = getFaceNormal(selectedFace)
    refPlane = adsk.core.Plane.create(selectedFace.vertices.item(0).geometry, normal)
    refLine = adsk.core.InfiniteLine3D.create(
        selectedFace.vertices.item(0).geometry, normal
    )
    refPoint = refPlane.intersectWithLine(refLine)
    faceList = []
    body = adsk.fusion.BRepBody.cast(selectedFace.body)
    for face in body.faces:
        if not normal.isParallelTo(getFaceNormal(face)):
            continue
        facePlane = adsk.core.Plane.create(face.vertices.item(0).geometry, normal)
        intersectionPoint = facePlane.intersectWithLine(refLine)
        #        distanceToRefPoint = refPoint.distanceTo(intersectionPoint)
        directionVector = refPoint.vectorTo(intersectionPoint)
        distance = directionVector.dotProduct(normal)
        #       distanceToRefPoint = distanceToRefPoint* (-1 if direction <0 else 1)
        faceList.append([face, distance])
    sortedFaceList = sorted(faceList, key=lambda x: x[1])
    top = sortedFaceList[-1]
    refPoint = (
        top[0].nativeObject.pointOnFace
        if top[0].assemblyContext
        else top[0].pointOnFace
    )

    return top[0], refPoint


# TODO: strange contract, boolean or Vector3D
def getTranslateVectorBetweenFaces(fromFace: adsk.fusion.BRepFace, toFace: adsk.fusion.BRepFace) -> adsk.core.Vector3D or bool:
    #   returns absolute distance

    normal = getFaceNormal(fromFace)
    if not normal.isParallelTo(getFaceNormal(fromFace)):
        return False

    fromFacePlane = adsk.core.Plane.create(fromFace.vertices.item(0).geometry, normal)
    fromFaceLine = adsk.core.InfiniteLine3D.create(
        fromFace.vertices.item(0).geometry, normal
    )
    fromFacePoint = fromFacePlane.intersectWithLine(fromFaceLine)

    toFacePlane = adsk.core.Plane.create(toFace.vertices.item(0).geometry, normal)
    toFacePoint = toFacePlane.intersectWithLine(fromFaceLine)
    translateVector = fromFacePoint.vectorTo(toFacePoint)
    return translateVector
