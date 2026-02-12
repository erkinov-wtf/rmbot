from importlib.util import find_spec

if find_spec("celery") is not None:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
else:
    __all__ = ()
