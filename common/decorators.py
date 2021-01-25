import logging, sys, gc
import weakref
import adsk.core, adsk.fusion
from typing import Callable, List, NamedTuple

from functools import wraps, lru_cache
from ..constants import *

class Handler(NamedTuple):
    handler: any
    event: any #weakref.ReferenceType
handlers: List[Handler] = []

logger = logging.getLogger('Nester.decorators')

# Decorator to add eventHandler
def eventHandler(handler_cls):
    def decoratorWrapper(notify_method):
        @wraps(notify_method)
        def handlerWrapper(orig_self, *handler_args, **handler_kwargs):

            event = handler_args[0]
            logger.debug(f'notify method created: {notify_method.__name__}')

            try:

                class _Handler(handler_cls):
                    def __init__(self):
                        super().__init__()

                    def notify( self, eventArgs):
                        try:
                            logger.debug(f'{notify_method.__name__} handler notified: {eventArgs.firingEvent.name}')
                            notify_method(orig_self, eventArgs)
                        except:
                            logger.exception(f'{eventArgs.firingEvent.name} error termination')
                h = _Handler()
                event.add(h)
                handlers.append(Handler(h, event)) #adds to global handlers list
            except:
                logger.exception(f'{handler_cls.name} handler creation error')
            return h
        return handlerWrapper
    return decoratorWrapper

# Decorator to add debugger dict Clearing
def clearDebuggerDict(method):
    def decoratorWrapper(*args, **kwargs):
        rtn = method(*args, **kwargs)
        sys.modules['_pydevd_bundle.pydevd_xml'].__dict__['_TYPE_RESOLVE_HANDLER']._type_to_resolver_cache = {}
        sys.modules['_pydevd_bundle.pydevd_xml'].__dict__['_TYPE_RESOLVE_HANDLER']._type_to_str_provider_cache = {}
        logger.debug(f'gc.collect count = {gc.collect()}')
        return rtn
    return decoratorWrapper

class Button(adsk.core.ButtonControlDefinition):
    def __init__():
        super().__init__()

    def addCmd(self, 
                parentDefinition, 
                commandId, 
                commandName, 
                tooltip, 
                resourceFolder,
                handlerMethod, 
                parentControl):
        commandDefinition_ = parentDefinition.itemById(commandId)

        if not commandDefinition_:
            commandDefinition_ = parentDefinition.addButtonDefinition(commandId, 
                                                                        commandName, 
                                                                        tooltip, 
                                                                        resourceFolder)
        
        handlerMethod(commandDefinition_.commandCreated)

        control_ = parentControl.addCommand(exportCommandDefinition_)
        exportControl_.isPromoted = True

        return commandDefinition_


def makeTempFaceVisible(method):
    @wraps(method)
    def wrapper (*args, **kwargs):

        # Create a base feature
        baseFeats = rootComp.features.baseFeatures
        baseFeat = baseFeats.add()
        
        baseFeat.startEdit()
        bodies = rootComp.bRepBodies

        tempBody = method(*args, **kwargs)
        tempBody.name = "Debug_" + method.__name__
        bodies.add(tempBody)

        baseFeat.finishEdit()
        return tempBody
    return wrapper

def entityFromToken(method):
    cacheDict = {}

    @wraps(method)
    def wrapper(*args, **kwargs):
        try:
            entityToken = method(*args, **kwargs)
            entity = cacheDict.setdefault(entityToken, design.findEntityByToken(entityToken)[0])
            return entity
        except:
            return None
    return wrapper


        


    
     
        

 
