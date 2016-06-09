#Author-Casey Rogers and Patrick Rainsberry and David Liu
#Description-An Add-In for making dog-bone fillets.

# Select edges interior to 90 degree angles. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diamater equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.
# Alternatively, select an entire body and the add-in will automatically apply a dog-bone to all interior vertical edges

from collections import defaultdict

import adsk.core, adsk.fusion
import math
import traceback

import time
from . import utils


class DogboneCommand(object):
    def __init__(self):
        self.app = adsk.core.Application.get()
        self.ui = self.app.userInterface

        self.offStr = "0"
        self.offVal = None
        self.circStr = "cutter"
        self.circVal = None
        self.yUp = False
        self.outputUnconstrainedGeometry = True
        self.edges = []
        self.benchmark = False

        # Note: we need to maintain a reference to each handler, otherwise the handlers will be GC'd and SWIG will be
        # unable to call our callbacks. Learned this the hard way!
        self.handlers = []  # needed to prevent GC of SWIG objects

    def addButton(self):
        # clean up any crashed instances of the button if existing
        try:
            self.removeButton()
        except:
            pass

        class CreateHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(handler):
                super(CreateHandler, handler).__init__()
                self.handlers.append(handler)  # needed to prevent GC of SWIG objects

            def notify(handler, args):
                try:
                    self.onCreate(args)
                    # Connect up to command related events.
                    args.command.execute.add(ExecHandler())
                    args.command.validateInputs.add(ValidateInputsHandler())
                except:
                    utils.messageBox(traceback.format_exc())

        class ExecHandler(adsk.core.CommandEventHandler):
            def __init__(handler):
                super(ExecHandler, handler).__init__()
                self.handlers.append(handler)  # needed to prevent GC of SWIG objects

            def notify(handler, args):
                try:
                    start = time.time()

                    self.onExecute(args)

                    if self.benchmark:
                        utils.messageBox("Benchmark: {:.02f} sec processing {} edges".format(
                            time.time() - start, len(self.edges)))
                except:
                    utils.messageBox(traceback.format_exc())

        class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
            def __init__(handler):
                super(ValidateInputsHandler, handler).__init__()
                self.handlers.append(handler)  # needed to prevent GC of SWIG objects

            def notify(handler, args):
                try:
                    self.onValidate(args)
                except:
                    utils.messageBox(traceback.format_exc())

        # add add-in to UI
        buttonDogbone = self.ui.commandDefinitions.addButtonDefinition(
            'dogboneBtn', 'Dogbone', 'Creates a dogbone at the corner of two lines/edges', 'Resources')

        buttonDogbone.commandCreated.add(CreateHandler())

        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        buttonControl = createPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

    def onCreate(self, args):
        inputs = args.command.commandInputs

        selInput0 = inputs.addSelectionInput(
            'select', 'Interior Edges or Solid Bodies',
            'Select the edge interior to each corner, or a body to apply to all internal edges')
        selInput0.addSelectionFilter('LinearEdges')
        selInput0.addSelectionFilter('SolidBodies')
        selInput0.setSelectionLimits(1,0)

        inp = inputs.addValueInput(
            'circDiameter', 'Tool Diameter', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.circStr))
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."

        inp = inputs.addValueInput(
            'offset', 'Additional Offset', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.offStr))
        inp.tooltip = "Additional increase to the radius of the dogbone."

        inp = inputs.addBoolValueInput("yUp", "Y-Up", True, "", self.yUp)
        inp.tooltip = "Controls which direction is vertical (parallel to cutter). " \
                      "Check this box to use Y, otherwise Z."

        inp = inputs.addBoolValueInput("outputUnconstrainedGeometry",
                                       "Output unconstrained geometry",
                                       True, "", self.outputUnconstrainedGeometry)
        inp.tooltip = "~5x faster, but non-parametric. " \
                      "If enabled, you'll have to delete and re-generate dogbones if geometry " \
                      "preceding dogbones is updated."

        inputs.addBoolValueInput("benchmark", "Benchmark running time", True, "", self.benchmark)

    def onExecute(self, args):
        command = args.firingEvent.sender

        # Get the data and settings from the command inputs.
        self.edges = []
        bodies = []
        for input in command.commandInputs:
            if input.id == 'circDiameter':
                self.circStr = input.expression
                self.circVal = input.value
            elif input.id == 'offset':
                self.offStr = input.expression
                self.offVal = input.value
            elif input.id == 'outputUnconstrainedGeometry':
                self.outputUnconstrainedGeometry = input.value
            elif input.id == 'yUp':
                self.yUp = input.value
            elif input.id == 'benchmark':
                self.benchmark = input.value
            elif input.id == 'select':
                for i in range(input.selectionCount):
                    selType = input.selection(i).entity.objectType
                    if selType == adsk.fusion.BRepBody.classType():
                        bodies.append(input.selection(i).entity)
                    elif selType == adsk.fusion.BRepEdge.classType():
                        self.edges.append(input.selection(i).entity)
            else:
                raise RuntimeError("Unhandled parameter " + input.id)


        for body in bodies:
            for bodyEdge in body.edges:
                if bodyEdge.geometry.objectType == adsk.core.Line3D.classType():
                    if utils.isVertical(bodyEdge, self.yUp):
                        # Check if its an internal edge
                        if utils.getAngleBetweenFaces(bodyEdge) < math.pi:
                            # Add edge to the selection
                            self.edges.append(bodyEdge)

        self.createConsolidatedDogbones()

    def onValidate(self, args):
        cmd = args.firingEvent.sender

        for input in cmd.commandInputs:
            if input.id == 'select':
                if input.selectionCount < 1:
                    args.areInputsValid = False
            elif input.id == 'circDiameter':
                if input.value <= 0:
                    args.areInputsValid = False

    def removeButton(self):
        cmdDef = self.ui.commandDefinitions.itemById('dogboneBtn')
        if cmdDef:
            cmdDef.deleteMe()
        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        cntrl = createPanel.controls.itemById('dogboneBtn')
        if cntrl:
            cntrl.deleteMe()

    @property
    def design(self):
        return self.app.activeProduct

    @property
    def rootComp(self):
        return self.design.rootComponent

    @property
    def rootComp(self):
        return self.design.rootComponent

    @property
    def originPlane(self):
        return self.rootComp.xZConstructionPlane if self.yUp \
            else self.rootComp.xYConstructionPlane

    #
    # The main algorithm
    #
    def createConsolidatedDogbones(self):
        if not self.design:
            raise RuntimeError('No active Fusion design')

        sketches = self.rootComp.sketches
        planes = self.rootComp.constructionPlanes
        extrudes = self.rootComp.features.extrudeFeatures

        startIndex = self.design.timeline.markerPosition

        progressDialog = self.ui.createProgressDialog()
        progressDialog.cancelButtonText = 'Cancel'
        progressDialog.isBackgroundTranslucent = False
        progressDialog.isCancelButtonShown = True
        progressDialog.show('Create Dogbones', "Computing edge groups (%m edges)", 0, len(self.edges))
        adsk.doEvents()

        progressMsg = '[%p%] %v / %m dogbones created'
        skipped = 0
        for (h0, h1), edges in self.groupEdgesByVExtent(self.edges).items():
            # Edges with the same vertical extent will be dogboned using one sketch + extrude-cut operation.
            progressDialog.message = "{}\nOperating on {} edges with extent {:.03f},{:.03f}".format(
                progressMsg, len(edges), h0, h1)
            adsk.doEvents()

            planeInput = planes.createInput()
            planeInput.setByOffset(self.originPlane, adsk.core.ValueInput.createByReal(h0))
            h0Plane = planes.add(planeInput)

            sketch = sketches.add(h0Plane)

            for edge, (cornerEdge0, cornerEdge1) in edges:
                if progressDialog.wasCancelled:
                    return

                if not utils.isVertical(edge, self.yUp):
                    progressDialog.progressValue += 1
                    skipped += 1
                    continue

                self.addDogboneCircle(cornerEdge0, cornerEdge1, sketch)

                progressDialog.progressValue += 1
                adsk.doEvents()

            progressDialog.message += "\nExtruding"
            adsk.doEvents()

            # Extrude-cut the dogbones
            profileColl = adsk.core.ObjectCollection.create()
            for prof in sketch.profiles:
                profileColl.add(prof)
            exInput = extrudes.createInput(profileColl, adsk.fusion.FeatureOperations.CutFeatureOperation)
            exInput.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h1 - h0))
            extrudes.add(exInput)

        progressDialog.message = "All done. Grouping timeline operations."
        adsk.doEvents()

        # group all the features we added
        endIndex = self.design.timeline.markerPosition - 1
        if endIndex > startIndex:  # at least two items to group
            self.design.timeline.timelineGroups.add(startIndex, endIndex)

        progressDialog.hide()

        if skipped:
            utils.messageBox("Skipped {} non-vertical edges".format(skipped))

    def addDogboneCircle(self, cornerEdge0, cornerEdge1, sketch):
        if self.outputUnconstrainedGeometry:
            # OPTIMIZATION: Directly compute where circle should go.
            # Don't use projected geometry, because it's slow.
            # Don't use sketch constraints, because it's slow.

            # Corner is defined by points c-a-b, a is where the edges meet.
            a, b, c = [sketch.modelToSketchSpace(p.geometry)
                       for p in utils.findPoints(cornerEdge0, cornerEdge1)]
            a.z = b.z = c.z = 0
            ab = a.vectorTo(b)
            ab.normalize()
            ac = a.vectorTo(c)
            ac.normalize()
            ad = ab.copy()
            ad.add(ac)
            ad.normalize()
            radius = self.circVal / 2 + self.offVal
            ad.scaleBy(radius)

            d = a.copy()
            d.translateBy(ad)
            sketch.sketchCurves.sketchCircles.addByCenterRadius(d, radius)

        else:
            # project the dogbone's corner onto the sketch
            line1 = sketch.project(cornerEdge0).item(0)
            line2 = sketch.project(cornerEdge1).item(0)

            # Corner is defined by points c-a-b, a is where the edges meet.
            a, b, c = utils.findPoints(line1, line2)

            # This is a temporary point for our Dogbone sketch's centerline to end at
            d = adsk.core.Point3D.create((b.geometry.x + c.geometry.x) / 2,
                                         (b.geometry.y + c.geometry.y) / 2, 0)
            line0 = sketch.sketchCurves.sketchLines.addByTwoPoints(a, d)

            line0.isConstruction = True
            line1.isConstruction = True
            line2.isConstruction = True
            # line0 should form line a-d that bisects angle c-a-b.
            sketch.geometricConstraints.addSymmetry(line1, line2, line0)

            # Constrain the length of the centerline to the radius of the desired dogbone
            length = sketch.sketchDimensions.addDistanceDimension(
                line0.startSketchPoint, line0.endSketchPoint,
                adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                utils.findMidPoint(line0))
            length.parameter.expression = self.circStr + "/ 2 + " + self.offStr

            # Create the dogbone's profile
            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(line0.endSketchPoint, self.circVal / 2)
            sketch.geometricConstraints.addCoincident(a, circle)

    def groupEdgesByVExtent(self, edges):
        """Group edges by their vertical extent, returning a dict where the keys are vertical extents
        (h0, h1 where h0 < h1), and the value is a list of edges that span that extent."""

        edgesByExtent = defaultdict(list)
        for edge in edges:
            approxExtent = self.normalizeVExtent(
                self.getH(edge.startVertex),
                self.getH(edge.endVertex))
            edgesByExtent[approxExtent].append((edge, utils.findCorner(edge)))

        # Now compute the true (unrounded) extent as the min and max of all extents in each group.
        edgesByTrueExtent = {}
        for approxExtent, edges in edgesByExtent.items():
            h0, h1 = 1e20, -1e20
            for e, corner in edges:
                h0 = min(h0, self.getH(e.startVertex), self.getH(e.endVertex))
                h1 = max(h1, self.getH(e.startVertex), self.getH(e.endVertex))
            edgesByTrueExtent[(h0, h1)] = edges

        return edgesByTrueExtent

    def getH(self, point):
        return point.geometry.y if self.yUp else point.geometry.z

    @staticmethod
    def normalizeVExtent(h0, h1):
        """Given a vertical extent (h0, h1), round the extent values and make sure they are ordered correctly.
        This makes them suitable for a hash key, as extents that are functionally identical (but different due to
        machine precision or reversed direction) will have the same key."""
        if h0 > h1:
            return round(h1, 5), round(h0, 5)
        else:
            return round(h0, 5), round(h1, 5)


dog = DogboneCommand()


def run(context):
    try:
        dog.addButton()
    except:
        utils.messageBox(traceback.format_exc())


def stop(context):
    try:
        dog.removeButton()
    except:
        utils.messageBox(traceback.format_exc())

