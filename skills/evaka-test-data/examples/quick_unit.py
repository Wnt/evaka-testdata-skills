#!/usr/bin/env python3
"""Template for the most common request, built with scripts/scenario.py:
"a daycare with three groups and 15 children with their attendance" (+ staff and shifts).
Copy, adjust names/counts, run. Written against eVaka 6eb51e0b (2026-10).

  python3 -B quick_unit.py --commit <appCommit> --today <YYYY-MM-DD> --now <HH:MM> \
      --area <careAreaId> --options '<json {placementType: serviceNeedOptionId}>' \
      --out payload.json [--rollback]
"""
import argparse
import json
import os
import sys
from datetime import timedelta

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from scenario import Scenario  # noqa: E402
from evaka_testdata import D  # noqa: E402

ap = argparse.ArgumentParser()
for arg in ("--commit", "--today", "--now", "--area", "--options"):
    ap.add_argument(arg, required=True)
ap.add_argument("--batch", default="quick-unit")
ap.add_argument("--out", default="payload.json")
ap.add_argument("--rollback", action="store_true")
a = ap.parse_args()
OPT = json.loads(a.options)  # e.g. {"DAYCARE": "...", "PRESCHOOL_DAYCARE": "..."} from get_environment_info
today = D(a.today)
term_end = D(f"{today.year + (today.month >= 8)}-07-31")

s = Scenario(commit=a.commit, today=a.today, now=a.now, seed=7)
u = s.unit("Päiväkoti Kalliorinne", a.area, ["Oravat", "Siilit", "Ketut"], preschool=True,
           address=("Kalliorinteentie 6", "02320"))
boss = s.employee("Riikka", "Mäkelä", u, "UNIT_SUPERVISOR", groups=["Siilit"], coefficient="0.00")
for first, last, group in [("Anniina", "Laaksonen", "Oravat"), ("Mervi", "Salo", "Oravat"),
                           ("Juho", "Nieminen", "Siilit"), ("Elina", "Rantanen", "Siilit"),
                           ("Sanna", "Heikkinen", "Ketut"), ("Aino", "Virtanen", "Ketut")]:
    s.employee(first, last, u, "STAFF", groups=[group])

# (guardians, children: (first, dob, sex, group, placement type, (arrive, leave)))
FAMILIES = [
    ([("Mikko", "Korhonen", "1987-05-22", "M"), ("Laura", "Korhonen", "1989-09-03", "F")],
     [("Eeli", "2020-03-14", "M", "Ketut", "PRESCHOOL_DAYCARE", ("07:45", "16:00")),
      ("Ilona", "2023-06-02", "F", "Oravat", "DAYCARE", ("07:45", "16:00"))]),
    ([("Jenni", "Virtanen", "1992-04-09", "F")], [("Aada", "2021-09-30", "F", "Siilit", "DAYCARE", ("08:00", "16:30"))]),
    ([("Abdi", "Ahmed", "1985-08-30", "M"), ("Hodan", "Ali", "1990-03-12", "F")],
     [("Yusuf", "2020-07-08", "M", "Ketut", "PRESCHOOL_DAYCARE", ("08:00", "15:00")),
      ("Amina", "2022-11-15", "F", "Siilit", "DAYCARE", ("08:30", "14:00"))]),
    ([("Ville", "Laine", "1990-07-07", "M"), ("Hanna", "Laine", "1991-01-25", "F")],
     [("Oliver", "2024-02-11", "M", "Oravat", "DAYCARE", ("08:00", "15:30"))]),
    ([("Petra", "Mäkinen", "1984-10-14", "F")], [("Venla", "2020-11-27", "F", "Ketut", "PRESCHOOL_DAYCARE", ("07:30", "16:30"))]),
    ([("Olga", "Smirnova", "1988-06-06", "F"), ("Antti", "Heino", "1986-11-19", "M")],
     [("Mila", "2021-04-04", "F", "Siilit", "DAYCARE", ("07:15", "15:45")),
      ("Eino", "2024-05-19", "M", "Oravat", "DAYCARE", ("08:30", "14:30"))]),
    ([("Tero", "Saarinen", "1983-03-03", "M"), ("Kaisa", "Saarinen", "1985-05-28", "F")],
     [("Lumi", "2020-02-02", "F", "Ketut", "PRESCHOOL", None)]),
    ([("Johanna", "Berg", "1993-02-14", "F"), ("Samuel", "Berg", "1992-09-09", "M")],
     [("Nooa", "2023-12-03", "M", "Oravat", "DAYCARE", ("08:30", "15:00")),
      ("Saga", "2020-09-15", "F", "Ketut", "PRESCHOOL_DAYCARE", ("08:30", "15:00"))]),
    ([("Riku", "Hämäläinen", "1989-04-01", "M"), ("Noora", "Hämäläinen", "1990-08-21", "F")],
     [("Elsa", "2022-06-17", "F", "Siilit", "DAYCARE", ("08:15", "16:00")),
      ("Topias", "2024-08-09", "M", "Oravat", "DAYCARE", ("08:00", "16:00"))]),
    ([("Minh", "Nguyen", "1986-02-17", "M"), ("Sofia", "Lindqvist", "1988-12-01", "F")],
     [("Leo", "2022-01-21", "M", "Siilit", "DAYCARE", ("07:30", "16:15"))]),
]
for guardians, kids in FAMILIES:
    fam = s.family(guardians)
    for first, dob, sex, group, ptype, times in kids:
        c = s.child(fam, first, dob, sex)
        start = "2026-08-11" if ptype.startswith("PRESCHOOL") else "2026-08-03"
        end = "2027-05-31" if ptype.startswith("PRESCHOOL") else term_end
        s.place(c, u, group, ptype, start, end, OPT[ptype], times=times, confirmed_by=boss)
        if first == "Leo":  # a family holiday next to some random sick days
            s.absence(c, today - timedelta(days=7), today - timedelta(days=5), "OTHER_ABSENCE")

two_weeks_ago = today - timedelta(days=today.weekday() + 14)
s.daily_life(two_weeks_ago, today + timedelta(days=11))
s.staff_shifts(two_weeks_ago, today + timedelta(days=4))
s.write(a.out, batch=a.batch, rollback=a.rollback)
