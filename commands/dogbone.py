# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

# Peter completely revamped the dogbone add-in by Casey Rogers and Patrick Rainsberry and David Liu
# Some of the original utilities have remained, but a lot of the other functionality has changed.

# The original add-in was based on creating sketch points and extruding - Peter found using sketches and extrusion to be very heavy
# on processing resources, so this version has been designed to create dogbones directly by using a hole tool. So far the
# the performance of this approach is day and night compared to the original version.

# Select the face you want the dogbones to drop from. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diameter equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.
import logging
import os
import sys

import adsk.core
import adsk.fusion

from ... import globalvars as g

_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f"{_appPath}", "py_packages")

if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    
from ...lib.classes import DbParams, Selection, DbParams, DogboneUi

from ...log import logger

import time
import traceback
from ...lib.utils import eventHandler, messageBox
from ...constants import DB_NAME, COMMAND_ID, UPD_COMMAND_ID
from .main import createStaticDogbones, updateDogBones

REV_ID = "revId"
ID = "id"
DEBUGLEVEL = logging.DEBUG

CONFIG_PATH = os.path.join(_appPath, "defaults.dat")
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')


# noinspection PyMethodMayBeStatic
class DogboneCommand(object):

    # def start(self, context):
    #     try:
    #         self.cleanup_commands()
    #         self.register_dialogcommand()
    #         self.register_updatecommand()
    #     except Exception as e:
    #         logger.exception(e)
    #         raise e

    # def stop(self, context):
    #     try:
    #         self.cleanup_commands()
    #     except Exception as e:
    #         logger.exception(e)
    #         raise e

    def write_defaults(self, param: DbParams):
        logger.info("config file write")
        self.write_file(CONFIG_PATH, param.to_json())

    def write_file(self, path: str, data: str):
        with open(path, "w", encoding="UTF-8") as file:
            file.write(data)

    def read_file(self, path: str) -> str:
        with open(path, "r", encoding="UTF-8") as file:
            return file.read()

    def read_defaults(self) -> DbParams:
        logger.info("config file read")

        if not os.path.isfile(CONFIG_PATH):
            return DbParams()

        try:
            json = self.read_file(CONFIG_PATH)
            return DbParams().from_json(json)
        except ValueError:
            return DbParams()

    # def register_dialogcommand(self):

    #     # Create button definition and command event handler
    #     button = g._ui.commandDefinitions.addButtonDefinition(
    #         COMMAND_ID,
    #         DB_NAME,
    #         "Creates dogbones at all inside corners of a face",
    #         ICON_FOLDER
    #     )

    #     self.onCreate(event=button.commandCreated)

    #     # Create controls for Manufacturing Workspace
    #     control = self.get_solid_create_panel().controls.addCommand(
    #         button, COMMAND_ID
    #     )

    #     # Make the button available in the Mfg panel.
    #     control.isPromotedByDefault = True
    #     control.isPromoted = True

    #     # Create button definition and command event handler
    #     createPanel = g._ui.allToolbarPanels.itemById("SolidCreatePanel")
    #     buttonControl = createPanel.controls.addCommand(button, COMMAND_ID)

    #     buttonControl.isPromotedByDefault = True
    #     buttonControl.isPromoted = True

    # def register_updatecommand(self):

    #     upd_button = g._ui.commandDefinitions.addButtonDefinition(
    #         UPD_COMMAND_ID,
    #         "DogboneUpdate",
    #         "Updates previously created dogbones",
    #         "resources/ui/update_button"
    #     )

    #     self.onUpdate(event=upd_button.commandCreated)

    #     # Make the button available in the Mfg panel.
    #     upd_control = self.get_solid_create_panel().controls.addCommand(
    #         upd_button,
    #         UPD_COMMAND_ID
    #     )

    #     upd_control.isPromotedByDefault = True
    #     upd_control.isPromoted = True
        
    #     # Create button definition and command event handler
    #     createPanel = g._ui.allToolbarPanels.itemById("SolidCreatePanel")
    #     upd_buttonControl = createPanel.controls.addCommand(upd_button, UPD_COMMAND_ID)

    #     upd_buttonControl.isPromotedByDefault = True
    #     upd_buttonControl.isPromoted = True

    @eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
    def onUpdate(self, args: adsk.core.CommandCreatedEventArgs):
        updateDogBones()

    @eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
    def onCreate(self, args: adsk.core.CommandCreatedEventArgs):
        """
        important persistent variables:
        self.selectedOccurrences  - Lookup dictionary
        key: activeOccurrenceId - hash of entityToken
        value: list of selectedFaces (DbFace objects)
            provides a quick lookup relationship between each occurrence and in particular which faces have been selected.

        self.selectedFaces - Lookup dictionary
        key: faceId =  - hash of entityToken
        value: [DbFace objects, ....]

        self.selectedEdges - reverse lookup
        key: edgeId - hash of entityToken
        value: [DbEdge objects, ....]
        """

        # global g._design

        if g._design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
            returnValue = g._ui.messageBox(
                "DogBone only works in Parametric Mode \n Do you want to change modes?",
                "Change to Parametric mode",
                adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                adsk.core.MessageBoxIconTypes.WarningIconType,
            )
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            g._design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        params = self.read_defaults()
        cmd: adsk.core.Command = args.command
        ui = DogboneUi(params, cmd, self.createDogbones)

    def createDogbones(self, params: DbParams, selection: Selection):
        start = time.time()

        self.write_defaults(params)
        createStaticDogbones(params, selection)

        #Remove check after F360 fixes their baseFeature/UI refresh issue  
        if g._ui.activeWorkspace.id == "MfgWorkingModelEnv":  
            g._ui.messageBox("If the tool bar becomes blank\nUse Undo then Redo (ctrl-z, ctrl-y)")

        logger.info(
            "all dogbones complete\n-------------------------------------------\n"
        )

        self.closeLogger()

        if params.benchmark:
            messageBox(
                f"Benchmark: {time.time() - start:.02f} sec processing {len(selection.edges)} edges"
            )

    # ==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    # ==============================================================================

    def closeLogger(self):
        for handler in logger.handlers:
            handler.flush()
            handler.close()

    @property
    def originPlane(self):
        return (
            g._rootComp.xZConstructionPlane if self.yUp else g._rootComp.xYConstructionPlane
        )