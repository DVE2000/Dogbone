import gc
import logging
import pprint
import sys
import time
import traceback
from dataclasses import dataclass, field
from functools import wraps
from typing import ClassVar, cast

import adsk.core
import adsk.fusion

# from . import common as g

# Globals
_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)
_ui = _app.userInterface
_rootComp = _design.rootComponent

pp = pprint.PrettyPrinter()

logger = logging.getLogger("dogbone.decorators")
logger.setLevel(logging.DEBUG)


@dataclass()
class HandlerCollection:
    """
    class to keep event handlers persistent
    It's not apparent if it's possible to figure which event each handler is attached to
    If you want to remove a handler selectively, you need both event and handler together.
    """

    handlers: ClassVar = field(init=False, default={})
    handler: None
    event: None
    group: str = "default"

    def __post_init__(self):
        HandlerCollection.handlers.setdefault(self.group, []).append(
            (self.event, self.handler)
        )

    @classmethod
    def str__(cls):
        result = "{"
        for group, groupList in cls.handlers.items():
            result += f"{group}: ["
            for event, handler in groupList:
                result += f"({event.name}, {handler} ),\n"
            result = result[:-2]
            result += " ]"
        result += " }"
        return result

    @classmethod
    def remove(cls, group=None):
        """
        Simple remove of group key and its values - python GC will clean up any orphaned handlers
        If parameter is None then do a complete HandlerCollection reset
        """
        if not group:
            cls.handlers = None
            return
        try:
            del cls.handlers[group]
        except KeyError:
            return

    # TODO - add selective eventHandler removal - might be more trouble than it's worth


# Decorator to add debugger dict Clearing
def clearDebuggerDict(method):
    def decoratorWrapper(*args, **kwargs):
        rtn = method(*args, **kwargs)
        sys.modules["_pydevd_bundle.pydevd_xml"].__dict__[
            "_TYPE_RESOLVE_HANDLER"
        ]._type_to_resolver_cache = {}
        sys.modules["_pydevd_bundle.pydevd_xml"].__dict__[
            "_TYPE_RESOLVE_HANDLER"
        ]._type_to_str_provider_cache = {}
        logger.debug(f"gc.collect count = {gc.collect()}")
        return rtn

    return decoratorWrapper


# Decorator to add eventHandler
def eventHandler(handler_cls=adsk.core.Base):
    """
    handler_cls is a subClass of EventHandler base class, which is not explicitly available.
    It must be user provided, and thus you can't declare the handler_cls to be of EventHandler type
    EventHandler Classes such as CommandCreatedEventHandler, or MouseEventHandler etc. are provided to ensure type safety
    """

    def decoratorWrapper(notify_method):
        @wraps(
            notify_method
        )  # spoofs wrapped method so that __name__, __doc__ (ie docstring) etc. behaves like it came from the method that is being wrapped.
        def handlerWrapper(
                *handler_args,
                event=adsk.core.Event,
                group: str = "default",
                **handler_kwargs,
        ):
            """When called returns instantiated _Handler
            - assumes that the method being wrapped comes from an instantiated Class method
            - inherently passes the "self" argument, if called method is in an instantiated class
            - kwarg "event" throws an error if not provided"""

            logger.debug(f"notify method created: {notify_method.__name__}")

            try:

                class _Handler(handler_cls):
                    name: str = f"{notify_method.__name__}_handler"

                    def notify(self, eventArgs):
                        try:
                            logger.debug(
                                f"{notify_method.__name__} handler notified: {eventArgs.firingEvent.name}"
                            )
                            notify_method(
                                *handler_args, eventArgs
                            )  # notify_method_self and eventArgs come from the parent scope
                            return
                        except Exception as e:
                            print(traceback.format_exc())
                            logger.exception(f"{self.name} error termination")

                    def __str__(self):
                        return self.name

                h = (
                    _Handler()
                )  # instantiates handler with the arguments provided by the decorator
                event.add(h)  # this is where the handler is added to the event

                # HandlerCollection.handlers.append(HandlerCollection(h, event))
                _ = HandlerCollection(group=group, handler=h, event=event)
                # print(_)
                # adds to class handlers list, needs to be persistent otherwise GC will remove the handler
                # - deleting handlers (if necessary) will ensure that garbage collection will happen.
            except Exception as e:
                logger.exception(e)
                print(f"{notify_method.__name__}: {traceback.format_exc()}")
                logger.exception(f"handler creation error {notify_method.__name__}")
            return h

        return handlerWrapper

    return decoratorWrapper


# Decorator to trigger parser
def parseDecorator(func):
    @wraps(
        func
    )  # spoofs wrapped method so that __name__, __doc__ (ie docstring) etc. behaves like it came from the method that is being wrapped.
    def wrapper(*_args, **_kwargs):
        """ """
        rtn = func(*_args, **_kwargs)
        cmdInputs = _args[1].inputs.command.commandInputs
        _args[0].parseInputs(cmdInputs)  # calls self.parseInputs - needs to be better
        logger.debug(f"notify method created: {func.__name__}")
        return rtn

    return wrapper


def makeTempFaceVisible(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        # Create a base feature
        baseFeats = _rootComp.features.baseFeatures
        baseFeat = baseFeats.add()

        baseFeat.startEdit()
        bodies = _rootComp.bRepBodies

        tempBody = method(*args, **kwargs)
        tempBody.name = f"Debug_{method.__name__}"
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
            entity = cacheDict.setdefault(
                entityToken, _design.findEntityByToken(entityToken)[0]
            )
            return entity
        except:
            return None

    return wrapper


def tokeniseEntity(method):
    @wraps(method)
    def wrapper(*args, entity: adsk.core.Base = adsk.core.Base, **kwargs):
        """
        Converts any entity passed in the parameters to its entityToken
        """
        newArgs = []
        newkwargs = {}
        for a in args:
            try:
                newArgs.append(a.entityToken)
            except AttributeError:
                newArgs.append(a)
                continue
        for k, v in kwargs:
            try:
                newkwargs[k] = v.entityToken
            except AttributeError:
                newArgs[k] = v
                continue
        result = method(*newArgs, **newkwargs)
        return result

    return wrapper


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        startTime = time.time()
        result = func(*args, **kwargs)
        logger.debug(f"{func.__name__}: time taken = {time.time() - startTime}")
        return result

    return wrapper
