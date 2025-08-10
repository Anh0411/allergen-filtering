try:  # Make celery optional for library-style imports/tests
    from .celery import app as celery_app  # type: ignore
    __all__ = ('celery_app',)
except Exception:  # pragma: no cover
    celery_app = None
    __all__ = ()
