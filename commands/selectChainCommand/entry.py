# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

import os
import logging

import adsk.core
import adsk.fusion
import logging
    
from ...lib.classes import DbParams, Selection, params

from ...lib.classes import SelectChainUi

from ...lib.common.log import startLogger, stopLogger

import time
from ...lib.utils import eventHandler, messageBox
from .main import createStaticDogbones
from ... import config

# logger = logging.getLogger('dogbone')

appPath = os.path.dirname(os.path.abspath(__file__))


CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdChainDialog'
CMD_CUSTOM_EVENT_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdChainSelectOpenEvent'
CMD_NAME = 'ChainSelect'
CMD_Description = 'Lets you select an open or closed chain from which dogbones are created'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
# WORKSPACE_ID = 'FusionSolidEnvironment'
# PANEL_ID = 'SolidCreatePanel'
# COMMAND_BESIDE_ID = ''

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(appPath, 'resources', '')

logger = logging.getLogger('dogbone.createCommand')

def start():
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    try:
        
        cmd_def =  ui.commandDefinitions.addButtonDefinition(
            CMD_ID,
            CMD_NAME,
            CMD_Description,
            ICON_FOLDER
        )
        
        onCreate(event=cmd_def.commandCreated)

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        # workspace = ui.workspaces.itemById(WORKSPACE_ID)

        # Get the panel the button will be created in.
        # panel = workspace.toolbarPanels.itemById(PANEL_ID)

        # Create the button command control in the UI after the specified existing command.
        # control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

        # Specify if the command is promoted to the main toolbar. 
        # control.isPromoted = params.isPromotedCreate


    except Exception as e:
        logger.exception(e)
        raise e

def stop():

    app = adsk.core.Application.get()
    ui = app.userInterface
    # Get the various UI elements for this command
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    # params.isPromotedCreate = command_control.isPromoted

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    stopLogger()


@eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
def onCreate( args: adsk.core.CommandCreatedEventArgs):
    from ...lib.classes import DogboneUi  #need to import main classes and functions here - to prevent InvalidDocument Error on start-up
    
    app = adsk.core.Application.get()
    design: adsk.fusion.Design = app.activeProduct
    ui = app.userInterface

    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        returnValue = ui.messageBox(
            "DogBone only works in Parametric Mode \n Do you want to change modes?",
            "Change to Parametric mode",
            adsk.core.MessageBoxButtonTypes.YesNoButtonType,
            adsk.core.MessageBoxIconTypes.WarningIconType,
        )
        if returnValue != adsk.core.DialogResults.DialogYes:
            return
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    cmd: adsk.core.Command = args.command
    # startLogger()
    ui = SelectChainUi(params, cmd, createStaticDogbones)
