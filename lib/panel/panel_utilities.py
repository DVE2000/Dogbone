from ...constants import COMMAND_ID, UPD_COMMAND_ID
# from ...globalvars import _ui

def get_solid_create_panel():
    env = _ui.workspaces.itemById("MfgWorkingModelEnv")
    tab = env.toolbarTabs.itemById("MfgSolidTab")
    return tab.toolbarPanels.itemById("SolidCreatePanel")

def cleanup_commands():
    remove_from_all()
    remove_from_solid()
    remove_command_definition()

def remove_from_all():
    panel = _ui.allToolbarPanels.itemById("SolidCreatePanel")
    if not panel:
        return

    command = panel.controls.itemById(COMMAND_ID)
    command and command.deleteMe()

    command = panel.controls.itemById(UPD_COMMAND_ID)
    command and command.deleteMe()

def remove_from_solid():
    control = get_solid_create_panel().controls.itemById(COMMAND_ID)
    control and control.deleteMe()

    control = get_solid_create_panel().controls.itemById(UPD_COMMAND_ID)
    control and control.deleteMe()

def remove_command_definition():
    if cmdDef := _ui.commandDefinitions.itemById(COMMAND_ID):
        cmdDef.deleteMe()

    if cmdDef := _ui.commandDefinitions.itemById(UPD_COMMAND_ID):
        cmdDef.deleteMe()
