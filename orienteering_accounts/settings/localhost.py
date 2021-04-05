import sys

from .base import *

LOGGING['loggers']['django']['handlers'] += ['console']
LOGGING['loggers']['orienteering_accounts']['handlers'] += ['console']

try:
    from .local import *
except ImportError:
    pass

if 'test' in sys.argv:
    try:
        from .unit_tests import *
    except ImportError:
        pass
