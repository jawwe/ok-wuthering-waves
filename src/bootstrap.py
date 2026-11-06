"""Keep this distribution independent of any enclosing legacy launcher."""
import os


def prepare_environment():
    for key in tuple(os.environ):
        if key.startswith("PYAPPIFY_"):
            del os.environ[key]
