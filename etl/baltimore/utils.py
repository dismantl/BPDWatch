import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from OpenOversight.app.models import db  # noqa E402

suffixes = [
    'Sr',
    'Jr',
    'II',
    '2nd',
    'III',
    '3rd',
    'IV',
    '4th'
]

name_re = re.compile(r"^(?P<last_name>[a-zA-Z- '\.]+?)(?: (?P<suffix>(?i:" + r"|".join(suffixes) + r"))\.?)?,(?P<first_name>[a-zA-Z- '\.]+?)(?: (?P<middle_initial>[a-zA-Z])\.?)?$")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)