import math, logging
import traceback, time

import adsk.core
import adsk.fusion
from collections import namedtuple

HoleParameters = namedtuple('HoleParameters',['centre','vertex', 'edge1','edge2', 'bottomFace'])

logger = logging.getLogger(__name__)

makeTopOcc = lambda x, y: x.nativeObject.createForAssemblyContext(y)
getOccName = lambda x: x.assemblyContext.name if x.assemblyContext else x.name
getFaceNormal = lambda face: face.evaluator.getNormalAtPoint(face.pointOnFace)[1]

class Root(object):
    def __init__(self, entity):
        self.root = entity.assemblyContext
        
        

#utility wrapper function to record how long a function takes
def timer(func):
    def wrapper(*args, **kwargs):
        startTime = time.time()
        result = func(*args, **kwargs)
        logger.debug('{}: time taken = {}'.format(func.__name__, time.time() - startTime))
        return result
    return wrapper

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

def getHoleLocationParameters(face:adsk.fusion.BRepFace, edge:adsk.fusion.BRepEdge, centreOffset):
    occ = face.assemblyContext
    edge = makeTopOcc(edge, occ)
    logger.debug('edge occurrence = {}'.format(getOccName(edge)))
    
    if not isEdgeAssociatedWithFace(face, edge):
        return False
#                continue  # skip if edge is not associated with the face currently being processed

    startVertex = adsk.fusion.BRepVertex.cast(getVertexAtFace(face, edge))
    logger.debug('start vertex occurrence = {}'.format(getOccName(startVertex)))
    extentToEntity = findExtent(face, edge)
    extentFaces = extentToEntity.faces
    startFaceNormal = face.evaluator.getNormalAtPoint(face.pointOnFace)
    for bFace in extentFaces:
        if not bFace.evaluator.getNormalAtPoint(bFace.pointOnFace)[1].isParallelTo(startFaceNormal[1]):
            continue
        bottomFace = bFace
        break
    
    logger.debug('extentToEntity occurrence = {}'.format(getOccName(extentToEntity)))

    logger.debug('extentToEntity - {}'.format(extentToEntity.isValid))

    try:
        (edge1, edge2) = getCornerEdgesAtFace(face.nativeObject, edge.nativeObject)
    except:
        logger.exception('Failed at findAdjecentFaceEdges')
        messageBox('Failed at findAdjecentFaceEdges:\n{}'.format(traceback.format_exc()))

    centrePoint = startVertex.geometry.copy()
    logger.debug('initial centrePoint = {}'.format(centrePoint.asArray()))
        
    selectedEdgeFaces = makeTopOcc(edge, occ).faces
    
    dirVect = adsk.core.Vector3D.cast(getFaceNormal(selectedEdgeFaces[0]).copy())
    dirVect.add(getFaceNormal(selectedEdgeFaces[1]))
    dirVect.normalize()
    dirVect.scaleBy(centreOffset)
 
    dirVect = adsk.core.Vector3D.cast(getFaceNormal(makeTopOcc(selectedEdgeFaces[0], occ)).copy())
    dirVect.add(getFaceNormal(makeTopOcc(selectedEdgeFaces[1], occ)))

    centrePoint.translateBy(dirVect)
    logger.debug('final centrePoint = {}'.format(centrePoint.asArray()))

    return HoleParameters(centrePoint, startVertex, edge1.createForAssemblyContext(occ), edge2.createForAssemblyContext(occ), bottomFace)
   
    
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
