import threading
from typing import Dict, Tuple, Any, TypeVar

T = TypeVar('T')


def singleton(cls_: T) -> T:
    """
    Decorator to make a class instance unique (singleton pattern).

    The decorated class will have only one instance created, and __init__
    will be called only once for that instance.

    Args:
        cls_: The class to make singleton

    Returns:
        The singleton-wrapped class

    Raises:
        Exception: If the class is already decorated with singleton
    """
    instance_infos: Dict[type, Tuple[Any, bool]] = {}
    _lock = threading.Lock()

    # Check if this exact class (not inherited) is already decorated
    if hasattr(cls_, "__is_singleton__") and "__is_singleton__" in cls_.__dict__:
        raise Exception(f"{cls_.__name__} is already a singleton")

    class _Singleton(cls_):
        __is_singleton__ = True

        def __new__(cls, *args, **kwargs):
            with _lock:
                instance_info = instance_infos.get(cls, None)
                if instance_info is not None:
                    instance = instance_info[0]
                else:
                    instance = cls_.__new__(cls)
                    instance_infos[cls] = (instance, True)
                return instance

        def __init__(self, *args, **kwargs):
            with _lock:
                instance_info = instance_infos[self.__class__]
                if instance_info[1]:
                    cls_.__init__(self, *args, **kwargs)
                    instance_infos[self.__class__] = (instance_info[0], False)

        @classmethod
        def reset_singleton(cls):
            """Reset singleton for testing purposes"""
            with _lock:
                instance_infos.pop(cls, None)

    _Singleton.__name__ = cls_.__name__
    _Singleton.__module__ = cls_.__module__
    _Singleton.__qualname__ = getattr(cls_, '__qualname__', cls_.__name__)

    return _Singleton
