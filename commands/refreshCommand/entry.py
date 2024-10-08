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
import os

import adsk.core
import adsk.fusion

# _appPath = os.path.dirname(os.path.abspath(__file__))
# _subpath = os.path.join(f"{_appPath}", "py_packages")

# if _subpath not in sys.path:
#     sys.path.insert(0, _subpath)
    
from ...log import logger

from ...lib.utils import eventHandler
from .main import updateDogBones
from ... import config

REV_ID = "revId"
ID = "id"

ICON_FOLDER = os.path.join(config.appPath, 'resources', '')
app = adsk.core.Application.get()
ui = app.userInterface

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_upd_cmd'
CMD_NAME = 'Dogbone refresh'
CMD_Description = 'Updates previously created dogbones'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')


def start():
    try:
        # cleanup_commands()
        cmd_def =  ui.commandDefinitions.addButtonDefinition(
            CMD_ID,
            CMD_NAME,
            CMD_Description,
            ICON_FOLDER
        )

        onUpdate(event=cmd_def.commandCreated)

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        workspace = ui.workspaces.itemById(WORKSPACE_ID)

        # Get the panel the button will be created in.
        panel = workspace.toolbarPanels.itemById(PANEL_ID)

        # Create the button command control in the UI after the specified existing command.
        control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

        # Specify if the command is promoted to the main toolbar. 
        control.isPromoted = IS_PROMOTED


    except Exception as e:
        logger.exception(e)
        raise e

def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

@eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
def onUpdate( args: adsk.core.CommandCreatedEventArgs):
    updateDogBones()