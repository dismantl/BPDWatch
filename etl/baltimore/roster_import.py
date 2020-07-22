import pandas as pd
import os
import sys
import csv
import re
from datetime import datetime
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from OpenOversight.app import create_app, models  # noqa E402
from OpenOversight.app.models import db  # noqa E402

CSV_FILENAME = 'rosters/11-13-19_Employee_Demographics_for_Distribution.csv'
DEPARTMENT_ID = 1

app = create_app('development')
db.app = app

jobs = []
code_to_job = {}
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
seq_no_re = re.compile(r"^[A-Z]\d\d\d$")


def parse_name(row):
    full_name = row['full_name']
    matches = name_re.fullmatch(full_name)
    try:
        last_name = matches.group('last_name')
        suffix = matches.group('suffix')
        first_name = matches.group('first_name')
        middle_initial = matches.group('middle_initial')
        assert first_name and last_name
    except:
        raise Exception(f'Unable to parse name {full_name}')
    row['first_name'] = first_name
    row['last_name'] = last_name
    row['suffix'] = suffix

    officer = models.Officer.query.filter_by(unique_internal_identifier=row['unique_internal_identifier']).one_or_none()
    if officer and officer.middle_initial and len(officer.middle_initial) > len(middle_initial):
        row['middle_initial'] = officer.middle_initial
    else:
        row['middle_initial'] = middle_initial
    return row


def job_code_to_title(row):
    job_code = row['job_code']
    job_title = row['job_title']
    try:
        job_title = code_to_job[job_code]
    except KeyError:
        job_title = job_title.replace(' EID','')  # No need to keep the EID distinction in BPD Watch
        if job_title not in jobs:
            raise Exception(f"Job title not found: {job_title}")
    else:
        job_title = job_title.replace(' - EID','')
    row['rank'] = job_title
    return row


def clean_gender(gender):
    if gender == 'N':
        gender = 'Not Sure'
    return gender


# Race not included in latest department-provided roster
def int_to_race(rint):
    if rint == 1:
        race = 'White'
    elif rint == 2:
        race = 'Black or African American'
    elif rint == 3:
        race = 'Hispanic'
    elif rint == 4:
        race = 'Asian/Pacific Islander'
    elif rint == 5:
        race = 'American Indian/Alaska Native'
    elif rint == 6:
        race = 'Not Applicable (Non-U.S.)'
    # elif rint == 7:
    else:
        race = 'Not Specified'
    return race


def clean_seq_no(row):
    if row['full_name'] == 'Alleyne,Danelle L':
        row['unique_internal_identifier'] = 'X666'
    elif row['full_name'] == 'Nelson,Norman A':
        row['unique_internal_identifier'] = 'Y666'
    elif row['full_name'] == 'Harrison,Michael S':  # Why the fuck does the Police Commissioner not have a sequence number??
        row['unique_internal_identifier'] = 'Z666'
    row['unique_internal_identifier'] = row['unique_internal_identifier'].replace('-','')
    if not seq_no_re.fullmatch(row['unique_internal_identifier']):
        raise Exception(f"Invalid sequence number {row['unique_internal_identifier']}")
    return row


def clean_assignment_date(row):
    assignment_date = None
    if not isinstance(row['promotion_date'], float) and row['promotion_date'].strip():
        assignment_date = datetime.strptime(row['promotion_date'], '%m/%d/%Y').date()
    elif not isinstance(row['rehire_date'], float) and row['rehire_date'].strip():
        assignment_date = datetime.strptime(row['rehire_date'], '%m/%d/%Y').date()
    
    if not isinstance(row['employment_date'], float) and row['employment_date'].strip() and not assignment_date:
        assignment_date = datetime.strptime(row['employment_date'], '%m/%d/%Y').date()
    
    row['star_date'] = assignment_date
    return row


@contextmanager
def transaction():
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    eprint('Loading job codes and titles')
    for filename in ['scraped_job_codes.csv', 'additional_job_codes.csv']:
        with open(os.path.join(os.path.dirname(__file__), filename), 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                code_to_job[int(row['Job Code'])] = row['Job Title']
                jobs.append(row['Job Title'])
    eprint("Importing raw roster", CSV_FILENAME)
    dirty = pd.read_csv(os.path.join(os.path.dirname(__file__), CSV_FILENAME))
    clean = pd.DataFrame()
    clean['full_name'] = dirty['Name']
    clean['unique_internal_identifier'] = dirty['SEQ#']
    eprint('Cleaning sequence numbers')
    clean = clean.apply(clean_seq_no, axis=1)
    eprint('Parsing names')
    clean = clean.apply(parse_name, axis=1)
    eprint('Setting gender')
    clean['gender'] = dirty['Gender'].apply(clean_gender)
    eprint('Setting rank')
    clean['job_code'] = dirty['Job Code']
    clean['job_title'] = dirty['Job Title']
    clean = clean.apply(job_code_to_title, axis=1)
    clean['employment_date'] = dirty['Service Date']
    clean['rehire_date'] = dirty['Rehire Date']
    clean['promotion_date'] = dirty['Promotion Date']
    eprint('Cleaning assignments')
    clean.apply(clean_assignment_date, axis=1)
    clean.insert(0, "department_id", DEPARTMENT_ID)
    
    del clean['full_name']
    del clean['rehire_date']
    del clean['promotion_date']
    del clean['job_code']
    del clean['job_title']
    
    clean.to_csv(sys.stdout, index=False)


if __name__ == '__main__':
    main()