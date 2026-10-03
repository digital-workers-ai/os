import importlib
import os
import sys
from pathlib import Path

ADVERSARIAL_ROOT = os.environ.get("ADVERSARIAL_ROOT", "/adversarial")


def adversarial():
    if not Path(f"{ADVERSARIAL_ROOT}/seeds/adversarial.py").is_file():
        return None
    if ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.adversarial")


def world():
    if not Path(f"{ADVERSARIAL_ROOT}/seeds/world/__init__.py").is_file():
        return None
    if ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.world")
