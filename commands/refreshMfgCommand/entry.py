# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

import os

import adsk.core
import adsk.fusion

from ...lib.common.log import logging

from ... import config

from ...lib.classes.DbData import DbParams, params

logger = logging.getLogger('dogbone.refreshMfgCommand')
app = adsk.core.Application.get()
ui = app.userInterface

appPath = os.path.dirname(os.path.abspath(__file__))

ICON_FOLDER = os.path.join(appPath, 'resources', '')

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_updCmd'
CMD_NAME = 'Dogbone refresh'
CMD_Description = 'Updates previously created dogbones'

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
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        env = ui.workspaces.itemById(WORKSPACE_ID)

        tab = env.toolbarTabs.itemById(TAB_ID)

        # Get the panel the button will be created in.
        panel = tab.toolbarPanels.itemById(PANEL_ID)

        # Create the button command control in the UI after the specified existing command.
        control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

        # Specify if the command is promoted to the main toolbar. 
        control.isPromoted = params.isPromotedRefreshMfg
        control.isPromotedByDefault = params.isPromotedRefreshMfg

    except Exception as e:
        logger.exception(e)
        raise e

def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control: adsk.core.CommandControl = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    params.isPromotedRefreshMfg = command_control.isPromoted
    params.write_defaults()

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()
