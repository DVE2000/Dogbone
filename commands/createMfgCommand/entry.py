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
    
from ...log import logger

from ... import config
app = adsk.core.Application.get()
ui = app.userInterface

ICON_FOLDER = os.path.join(config.appPath, 'resources', '')

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdDialog'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'MfgWorkingModelEnv'
TAB_ID = 'MfgSolidTab'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = ''

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')


def start():
    try:
        cmd_def =  ui.commandDefinitions.itemById(CMD_ID)

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        env = ui.workspaces.itemById(WORKSPACE_ID)

        tab = env.toolbarTabs.itemById(TAB_ID)

        # Get the panel the button will be created in.
        panel = tab.toolbarPanels.itemById(PANEL_ID)

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
