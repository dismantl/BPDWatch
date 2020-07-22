import csv
import os
import sys
import re
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from OpenOversight.app import create_app, models  # noqa E402
from OpenOversight.app.models import db  # noqa E402

app = create_app('development')
db.app = app

@contextmanager
def transaction():
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

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

name_re = re.compile(r"^(?P<last_name>[a-zA-Z- '\.]+?)(?: (?P<suffix>(?i:" + r"|".join(suffixes) + r"))\.?)?$")
middle_initial_re = re.compile(r"^(?P<middle_initial>[A-Z])\.$")

if __name__ == '__main__':
    with transaction():
        last_names = 0
        middle_names = 0
        for officer in models.Officer.query.all():

            # Fix last name
            matches = name_re.fullmatch(officer.last_name)
            try:
                last_name = matches.group('last_name')
                assert last_name
                suffix = matches.group('suffix')
            except:
                raise Exception(f'Unable to parse last name {officer.last_name}')
            if suffix:
                print(f'Updating [{last_name}] [{suffix}]')
                officer.last_name = last_name
                officer.suffix = suffix
                last_names += 1
            else:
                officer.suffix = None
            
            # Fix middle names/initials
            if officer.middle_initial == '':
                officer.middle_initial = None
            if officer.middle_initial:
                matches = middle_initial_re.fullmatch(officer.middle_initial)
                if matches:
                    officer.middle_initial = matches.group('middle_initial')
                    middle_names += 1

    print(f'Updated {last_names} officer last names')
    print(f'Updated {middle_names} officer middle names/initials')