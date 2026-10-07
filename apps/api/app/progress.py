"""Per-worker progress; never attach request-specific state to the shared generator."""
from contextvars import ContextVar

progress_callback = ContextVar("generation_progress", default=None)


def report_progress(stage):
    callback = progress_callback.get()
    if callback is not None:
        callback(stage)
