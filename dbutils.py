import math, logging
import traceback

import adsk.core
import adsk.fusion


def getAngleBetweenFaces(edge):
    # Verify that the two faces are planar.
    face1 = edge.faces.item(0)
    face2 = edge.faces.item(1)
    if face1 and face2:
        if face1.geometry.objectType != adsk.core.Plane.classType() or face2.geometry.objectType != adsk.core.Plane.classType():
            return 0
    else:
        return 0

    # Get the normal of each face.
    ret = face1.evaluator.getNormalAtPoint(face1.pointOnFace)
    normal1 = ret[1]
    ret = face2.evaluator.getNormalAtPoint(face2.pointOnFace)
    normal2 = ret[1]
    # Get the angle between the normals.
    normalAngle = normal1.angleTo(normal2)

    # Get the co-edge of the selected edge for face1.
    if edge.coEdges.item(0).loop.face == face1:
        coEdge = edge.coEdges.item(0)
    elif edge.coEdges.item(1).loop.face == face1:
        coEdge = edge.coEdges.item(1)

    # Create a vector that represents the direction of the co-edge.
    if coEdge.isOpposedToEdge:
        edgeDir = edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
    else:
        edgeDir = edge.endVertex.geometry.vectorTo(edge.startVertex.geometry)

    # Get the cross product of the face normals.
    cross = normal1.crossProduct(normal2)

    # Check to see if the cross product is in the same or opposite direction
    # of the co-edge direction.  If it's opposed then it's a convex angle.
    if edgeDir.angleTo(cross) > math.pi/2:
        angle = (math.pi * 2) - (math.pi - normalAngle)
    else:
        angle = math.pi - normalAngle

    return angle

def findExtent(face, edge):
    
#    faceNormal = adsk.core.Vector3D.cast(face.evaluator.getNormalAtPoint(face.pointOnFace)[1])
    
    if edge.startVertex in face.vertices:
        endVertex = edge.endVertex
    else:
        endVertex = edge.startVertex
    return endVertex

    
def correctedEdgeVector(edge, refVertex):
    if edge.startVertex.geometry.isEqualTo(refVertex.geometry):
        return edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
    else:
        return edge.endVertex.geometry.vectorTo(edge.startVertex.geometry)
    return False

def correctedSketchEdgeVector(edge, refPoint):
    if edge.startSketchPoint.geometry.isEqualTo(refPoint.geometry):
        return edge.startSketchPoint.geometry.vectorTo(edge.endSketchPoint.geometry)
    else:
        return edge.endSketchPoint.geometry.vectorTo(edge.startSketchPoint.geometry)
    return False
    

def isEdgeAssociatedWithFace(face, edge):
    
    # have to check both ends - not sure which way around the start and end vertices are
    if edge.startVertex in face.vertices:
        return True
    if edge.endVertex in face.vertices:
        return True
    return False
    
def getCornerEdgesAtFace(face, edge):
    #not sure which end is which - so test edge ends for inclusion in face
    if edge.startVertex in face.vertices:
        startVertex = edge.startVertex
    else:
        startVertex = edge.endVertex 
    #edge has 2 adjacent faces - therefore the face that isn't from the 3 faces of startVertex, has to be the top face edges
#    returnVal = [edge1 for edge1 in edge.startVertex.edges if edge1 in face.edges]
    logger = logging.getLogger(__name__)
    returnVal = []
    for edge1 in startVertex.edges:
        if edge1 not in face.edges:
            continue
        logger.debug('edge {} added to adjacent edge list'.format(edge1.tempId))
        returnVal.append(edge1)
    if len(returnVal)!= 2:
        raise NameError('returnVal len != 2')
        
    return (returnVal[0], returnVal[1])
    
def getVertexAtFace(face, edge):
    if edge.startVertex in face.vertices:
        return edge.startVertex
    else:
        return edge.endVertex
    return False
    
def getFaceNormal(face):
    return face.evaluator.getNormalAtPoint(face.pointOnFace)[1]
    
    
def messageBox(*args):
    adsk.core.Application.get().userInterface.messageBox(*args)


def getTopFace(selectedFace):
    normal = getFaceNormal(selectedFace)
    refPlane = adsk.core.Plane.create(selectedFace.vertices.item(0).geometry, normal)
    refLine = adsk.core.InfiniteLine3D.create(selectedFace.vertices.item(0).geometry, normal)
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
    sortedFaceList = sorted(faceList, key = lambda x: x[1])
    top = sortedFaceList[-1]
    refPoint = top[0].nativeObject.pointOnFace if top[0].assemblyContext else top[0].pointOnFace
    
    return (top[0], refPoint)
 

def getTranslateVectorBetweenFaces(fromFace, toFace):
#   returns absolute distance
    logger = logging.getLogger(__name__)

    normal = getFaceNormal(fromFace)
    if not normal.isParallelTo(getFaceNormal(fromFace)):
        return False

    fromFacePlane = adsk.core.Plane.create(fromFace.vertices.item(0).geometry, normal)
    fromFaceLine = adsk.core.InfiniteLine3D.create(fromFace.vertices.item(0).geometry, normal)
    fromFacePoint = fromFacePlane.intersectWithLine(fromFaceLine)
    
    toFacePlane = adsk.core.Plane.create(toFace.vertices.item(0).geometry, normal)
    toFacePoint = toFacePlane.intersectWithLine(fromFaceLine)
    translateVector = fromFacePoint.vectorTo(toFacePoint)
    return translateVector
        
    
class HandlerHelper(object):
    def __init__(self):
        # Note: we need to maintain a reference to each handler, otherwise the handlers will be GC'd and SWIG will be
        # unable to call our callbacks. Learned this the hard way!
        self.handlers = []  # needed to prevent GC of SWIG objects

    def make_handler(self, handler_cls, notify_method, catch_exceptions=True):
        class _Handler(handler_cls):
            def notify(self, args):
                self.logger = logging.getLogger(__name__)
                if catch_exceptions:
                    try:
                        notify_method(args)
                    except:
                        messageBox('Failed:\n{}'.format(traceback.format_exc()))
                        self.logger.exception('error termination')
                        for handler in self.logger.handlers:
                            handler.flush()
                            handler.close()
                else:
                    notify_method(args)
        h = _Handler()
        self.handlers.append(h)
        return h
