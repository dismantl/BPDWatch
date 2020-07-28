import pandas as pd
import os
import sys
import glob
import re
import numpy
from datetime import date
from utils import name_re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from OpenOversight.app import create_app  # noqa E402
from OpenOversight.app.models import db, Officer, Salary  # noqa E402
from OpenOversight.app.utils import prompt_yes_no

app = create_app('development')
db.app = app

# 2020-7-27 import
problem_officers = [
    'F956',
    'T819',
    'K238',
    'K175',
    'K130',
    'K182',
    'T828',
    'K074',
    'K235',
    'J351',
    'T964',
    'T905'
]

NAME_COL = 0
AGENCY_ID_COL = 2
HIRE_DATE_COL = 4
SALARY_COL = 5
TOTAL_PAY_COL = 6


class SalaryImportLog:
    updated_officers = {}

    @classmethod
    def log_change(cls, officer, msg):
        if officer.id not in cls.updated_officers:
            cls.updated_officers[officer.id] = []
        log = cls.updated_officers[officer.id]
        log.append(msg)

    @classmethod
    def print_logs(cls):
        officers = Officer.query.filter(
            Officer.id.in_(cls.updated_officers.keys())).all()
        for officer in officers:
            print('Updates to officer {}:'.format(officer))
            for msg in cls.updated_officers[officer.id]:
                print(' --->', msg)


def add_salary(officer, rows, year):
    row = rows.loc[rows.first_valid_index()]

    if type(row[SALARY_COL]) == str:
        annual_salary = float(row[SALARY_COL].replace('$', ''))
    elif type(row[SALARY_COL]) == float or type(row[SALARY_COL]) == numpy.float64:
        annual_salary = row[SALARY_COL]
    else:
        raise Exception(type(row[SALARY_COL]))

    if type(row[TOTAL_PAY_COL]) == str:
        overtime_pay = float(row[TOTAL_PAY_COL].replace('$', '')) - annual_salary
    elif type(row[TOTAL_PAY_COL]) == float or type(row[TOTAL_PAY_COL]) == numpy.float64:
        if numpy.isnan(row[TOTAL_PAY_COL]):
            overtime_pay = 0
        else:
            overtime_pay = row[TOTAL_PAY_COL] - annual_salary

    salary = Salary(
        officer_id=officer.id,
        salary=annual_salary,
        overtime_pay=overtime_pay or None,
        year=year,
        is_fiscal_year=True
    )
    db.session.add(salary)
    SalaryImportLog.log_change(
        officer,
        f'Added salary for FY{year}: Salary {annual_salary}, Overtime {overtime_pay}'
    )


def import_salaries(directory):
    salary_sets = {}
    print("Processing salary charts")
    for csvfile in glob.glob(directory + '/*.csv'):
        year = int(re.search(r'20\d\d', csvfile).group(0))
        # read in CSV, parse out parts of name
        df = pd.read_csv(csvfile)
        # # Only want A99 department IDs
        df = df[df.iloc[:, AGENCY_ID_COL].str.startswith('A99')]
        # Skip officers with redacted names
        df = df[~df.iloc[:, NAME_COL].str.startswith('BPD ')]
        # Split name into multiple columns
        df = df.join(df.iloc[:, 0].str.extract(name_re))

        salary_sets[year] = df

    print("Importing salaries (this may take a while)")
    try:
        # foreach officer in DB, go matching
        for officer in Officer.query.all():
            added_salaries = False
            # print(officer)
            officer_salary_years = [salary.year for salary in officer.salaries]
            for year, df in salary_sets.items():
                # Don't check for salaries for years we already have data
                if year not in officer_salary_years:
                    # Match on first name, last name
                    rows = df[df['first_name'].fillna('').str.lower().str.match(officer.first_name.lower())]\
                        [lambda df: df['last_name'].fillna('').str.lower().str.match(officer.last_name.lower())]
                    if rows.empty:
                        continue
                    elif len(rows) == 1:
                        added_salaries = True
                        add_salary(officer, rows, year)
                    elif len(rows) > 1:
                        # Match on (first letter of) middle initial
                        if officer.middle_initial:
                            rows = rows[rows['middle_initial'].fillna('').str.upper().str.startswith(officer.middle_initial[:1].upper())]
                        else:
                            rows = rows[rows['middle_initial'].isna()]
                        if len(rows) == 1:
                            added_salaries = True
                            add_salary(officer, rows, year)
                        elif len(rows) > 1:
                            # Match on (equivalent) suffix
                            if officer.suffix:
                                officer_suffix = officer.suffix\
                                    .lower()\
                                    .replace('jr', 'ii')\
                                    .replace('2nd', 'ii')\
                                    .replace('3rd', 'iii')\
                                    .replace('4th', 'iv')
                            else:
                                officer_suffix = ''
                            rows = rows[rows['suffix']\
                                .fillna('')\
                                .str.lower()\
                                .str.replace('.', '')\
                                .str.replace('jr', 'ii')\
                                .str.replace('2nd', 'ii')\
                                .str.replace('3rd', 'iii')\
                                .str.replace('4th', 'iv')\
                                .str.match(officer_suffix)]
                            if len(rows) == 1:
                                added_salaries = True
                                add_salary(officer, rows, year)
                            else:
                                # Match on hiring date
                                hire_date = officer.employment_date.strftime('%m/%d/%Y')
                                rows = rows[rows.iloc[:, HIRE_DATE_COL].str.startswith(hire_date)]
                                if len(rows) == 1:
                                    added_salaries = True
                                    add_salary(officer, rows, year)
                                else:
                                    if officer.unique_internal_identifier not in problem_officers:
                                        raise Exception(
                                            'Could not match on suffix or hire date for {} {} {} {}'.format(
                                                officer.first_name, officer.middle_initial,
                                                officer.last_name, officer.suffix))
            if not added_salaries and len(officer.salaries) == 0:
                if officer.employment_date < date(year=2019, month=1, day=1) and officer.unique_internal_identifier not in problem_officers:
                    raise Exception(f'Officer {officer.last_name},{officer.first_name} ({officer.unique_internal_identifier}) not found in salary charts')
        
        print("Proposed changes:")
        SalaryImportLog.print_logs()
        if prompt_yes_no("Do you want to commit the above changes?"):
            print("Commiting changes.")
            db.session.commit()
        else:
            print("Aborting changes.")
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise


if __name__ == '__main__':
    import_salaries(sys.argv[1])
