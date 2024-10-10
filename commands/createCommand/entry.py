# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

import os
import logging

import adsk.core
import adsk.fusion
import logging
    
from ...lib.classes import DbParams, Selection, DbParams

from ...lib.common.log import startLogger, stopLogger

import time
from ...lib.utils import eventHandler, messageBox
from .main import createStaticDogbones
from ... import config

# logger = logging.getLogger('dogbone')

appPath = os.path.dirname(os.path.abspath(__file__))

ICON_FOLDER = os.path.join(appPath, 'resources', '')

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdDialog'
CMD_NAME = 'Dogbones'
CMD_Description = 'Creates dogbones at all inside corners of a face'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = ''

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

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

    app = adsk.core.Application.get()
    ui = app.userInterface
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

        stopLogger()


@eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
def onCreate( args: adsk.core.CommandCreatedEventArgs):
    from ...lib.classes import DogboneUi  #need to import main classes and functions here - to prevent InvalidDocument Error on start-up
    
    def read_file( path: str) -> str:
        with open(path, "r", encoding="UTF-8") as file:
            return file.read()

    def read_defaults() -> DbParams:
        logger.info("config file read")

        if not os.path.isfile(config.CONFIG_PATH):
            return DbParams()

        try:
            json = read_file(config.CONFIG_PATH)
            return DbParams().from_json(json)
        except ValueError:
            return DbParams()
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

    params = read_defaults()
    cmd: adsk.core.Command = args.command
    # startLogger()
    ui = DogboneUi(params, cmd, createDogbones)


def createDogbones( params: DbParams, selection: Selection):
    logger = logging.getLogger('dogbone.createDogbones')
    app = adsk.core.Application.get()
    ui = app.userInterface
    def write_defaults( param: DbParams):
        logger.info("config file write")
        write_file(config.CONFIG_PATH, param.to_json())

    def write_file( path: str, data: str):
        with open(path, "w", encoding="UTF-8") as file:
            file.write(data)

    start = time.time()

    write_defaults(params)
    createStaticDogbones(params, selection)

    #Remove check after F360 fixes their baseFeature/UI refresh issue  
    if  ui.activeWorkspace.id == "MfgWorkingModelEnv":  
         ui.messageBox("If the tool bar becomes blank\nUse Undo then Redo (ctrl-z, ctrl-y)")

    logger.info(
        "all dogbones complete\n-------------------------------------------\n"
    )

    if params.benchmark:
        messageBox(
            f"Benchmark: {time.time() - start:.02f} sec processing {len(selection.edges)} edges"
        )
    # stopLogger()