import math
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


# Returns points A, B, C where A is shared between the two input edges
def findPoints(edge0, edge1):
    if edge0.classType() == 'adsk::fusion::SketchLine':
        point0_0 = edge0.startSketchPoint
        point0_1 = edge0.endSketchPoint
        point1_0 = edge1.startSketchPoint
        point1_1 = edge1.endSketchPoint
    else:
        point0_0 = edge0.startVertex
        point0_1 = edge0.endVertex
        point1_0 = edge1.startVertex
        point1_1 = edge1.endVertex
    if (point0_0 == point1_0):
        pointA = point0_0
        pointB = point0_1
        pointC = point1_1
    elif (point0_0 == point1_1):
        pointA = point0_0
        pointB = point0_1
        pointC = point1_0
    elif (point0_1 == point1_0):
        pointA = point0_1
        pointB = point0_0
        pointC = point1_1
    elif (point0_1 == point1_1):
        pointA = point0_1
        pointB = point0_0
        pointC = point1_0
    else:
        raise RuntimeError("findPoints called on non-adjacent edges")

    return pointA, pointB, pointC


# Return MIDPOINT of LINE
def findMidPoint(line):
    x0 = line.startSketchPoint.geometry
    x1 = line.endSketchPoint.geometry
    y0 = x0.y
    y1 = x1.y
    x0 = x0.x
    x1 = x1.x
    midPoint = adsk.core.Point3D.create((x0 + x1)/2, (y0 + y1)/2, 0)
    return midPoint


# Finds and returns two EDGES that form a corner adjacent to EDGE
def findCorner(edge):
    # XXX(dliu): Is there a way to get adjacent edges directly instead of going from edge => face => edges?
    faces = edge.faces
    edges0 = faces.item(0).edges
    edges1 = faces.item(1).edges
    for e0 in edges0:
        if e0 == edge:
            continue
        for e1 in edges1:
            if e1 == edge:
                continue
            a0, a1 = e0.startVertex, e0.endVertex
            b0, b1 = e1.startVertex, e1.endVertex
            if a0 == b0 or a0 == b1 or a1 == b0 or a1 == b1:
                return e0, e1
    raise RuntimeError("findCorner called on non-adjacent edges")


# Check if edge is vertical
def isVertical(e, yup):
    if yup:
        return math.fabs(e.geometry.startPoint.x - e.geometry.endPoint.x) < .00001 \
               and math.fabs(e.geometry.startPoint.z - e.geometry.endPoint.z) <.00001
    return math.fabs(e.geometry.startPoint.x - e.geometry.endPoint.x) < .00001 \
           and math.fabs(e.geometry.startPoint.y - e.geometry.endPoint.y) <.00001


# Return centerpoint for dogbone when using boneDirection #points[0] is the shared point
def findDogboneCenterPoint(direction, radius, *points):
    longestIndex = 2
   
    # Assume along longest and that longest line is the line using points[2]. Find longest line first. 
    if (math.hypot(math.fabs(points[0].geometry.x - points[1].geometry.x), 
                    math.fabs(points[0].geometry.y - points[1].geometry.y)) >= 
         math.hypot(math.fabs(points[0].geometry.x - points[2].geometry.x), 
                    math.fabs(points[0].geometry.y - points[2].geometry.y))):
        longestIndex = 1

    # If along shortest, just switch longest and shortest. What's in a name?
    if (direction == 'shortest'):
        longestIndex = (~longestIndex) & 3 # switch 1 to 2 or vice-versa

    shortestIndex = (~longestIndex) & 3

    angle = math.atan2(math.fabs(points[0].geometry.y - points[longestIndex].geometry.y), 
                       math.fabs(points[0].geometry.x - points[longestIndex].geometry.x))

    # Adjust for non-vertical and non-horizontal mortises with trig
    addX = (radius / 2.0) * math.sin(angle)
    addY = (radius / 2.0) * math.cos(angle)

    # Figure out direction to move on "shortest" line
    if points[0].geometry.y > points[shortestIndex].geometry.y:
        addY *= -1.0
    if points[0].geometry.x > points[shortestIndex].geometry.x:
        addX *= -1.0

    return addX, addY, shortestIndex


def messageBox(*args):
    adsk.core.Application.get().userInterface.messageBox(*args)


class HandlerHelper(object):
    def __init__(self):
        # Note: we need to maintain a reference to each handler, otherwise the handlers will be GC'd and SWIG will be
        # unable to call our callbacks. Learned this the hard way!
        self.handlers = []  # needed to prevent GC of SWIG objects

    def make_handler(self, handler_cls, notify_method, catch_exceptions=True):
        class _Handler(handler_cls):
            def notify(self, args):
                if catch_exceptions:
                    try:
                        notify_method(args)
                    except:
                        messageBox('Failed:\n{}'.format(traceback.format_exc()))
                else:
                    notify_method(args)
        h = _Handler()
        self.handlers.append(h)
        return h
