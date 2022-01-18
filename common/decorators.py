import logging, sys, gc
from tkinter.messagebox import NO
import weakref
import adsk.core, adsk.fusion
from typing import Callable, List, ClassVar
from dataclasses import dataclass, field

from functools import wraps, lru_cache

logger = logging.getLogger('dogbone.decorators')
@dataclass
class HandlerCollection():
    '''
    class to keep event handles persistent
    '''
    handlers: ClassVar[List] = []
    handler: adsk.core.Base #
    event: adsk.core.Event

# Decorator to add eventHandler
def eventHandler(handler_cls=adsk.core.Base):
    '''
    handler_cls is a subClass of EventHandler base class, which is not explicitly available
    it is user provided
    EventHandler Classes such as CommandCreatedEventHandler, or MouseEventHandler etc. as provided to ensure type safety
    '''
    def decoratorWrapper(notify_method):
        @wraps(notify_method)  #spoofs wrapped method so that __name__, __doc__ (ie docstring) etc. behaves like it came from the method that is being wrapped.   
        def handlerWrapper( notify_method_self, *handler_args, event=adsk.core.Event, **handler_kwargs):
            '''When called returns instantiated _Handler 
                - assumes that the method being wrapped comes from an instantiated Class method
                - needs to pass the "self" argument
                - kwarg "event" throws an error if not provided '''

            logger.debug(f'notify method created: {notify_method.__name__}')

            try:

                class _Handler(handler_cls):

                    def notify( self, eventArgs):
                        try:
                            logger.debug(f'{notify_method.__name__} handler notified: {eventArgs.firingEvent.name}')
                            notify_method(notify_method_self, eventArgs)  #notify_method_self and eventArgs come from the parent scope
                        except:
                            logger.exception(f'{eventArgs.firingEvent.name} error termination')
                h = _Handler() #instantiates handler with the arguments provided by the decorator
                event.add(h)  #this is where the handler is added to the event
                HandlerCollection.handlers.append(HandlerCollection(h, event)) #adds to class handlers list, needs to be persistent otherwise GC will remove the handler - deleting handlers (if necessary) will ensure that garbage collection will happen.
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


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        startTime = time.time()
        result = func(*args, **kwargs)
        logger.debug('{}: time taken = {}'.format(func.__name__, time.time() - startTime))
        return result
    return wrapper     


    
     
        

 
