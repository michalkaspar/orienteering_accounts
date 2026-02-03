import sys

from .base import *

try:
    from .local import *
except ImportError:
    pass

if 'test' in sys.argv:
    try:
        from .unit_tests import *
    except ImportError:
        pass
