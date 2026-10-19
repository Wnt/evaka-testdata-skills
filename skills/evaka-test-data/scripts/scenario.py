"""High-level builders for the most common scenario: a unit with groups and staff, families with
children placed in it, and their everyday data (reservations, absences, attendance, staff
shifts). A typical request becomes a ~30 line script; anything else is added with `s.rows.add()`.

Builders write plain dicts with the fields that have been stable in eVaka for years. Every
builder takes **extra fields that override or extend the row, so a renamed or new field never
blocks you. Always run row_types.py --check and the rollback validation as usual.

    from scenario import Scenario
    s = Scenario(commit=APP_COMMIT, today="2026-10-19", now="10:50", seed=1)
    u = s.unit("Päiväkoti Kalliorinne", AREA_ID, ["Oravat", "Siilit", "Ketut"], preschool=True)
    boss = s.employee("Riikka", "Mäkelä", u, "UNIT_SUPERVISOR", groups=["Siilit"], coefficient="0.00")
    t = s.employee("Anniina", "Laaksonen", u, "STAFF", groups=["Oravat"])
    f = s.family([("Mikko", "Korhonen", "1987-05-22", "M"), ("Laura", "Korhonen", "1989-09-03", "F")])
    c = s.child(f, "Eeli", "2020-03-14", "M")
    s.place(c, u, "Ketut", "PRESCHOOL_DAYCARE", "2026-08-11", "2027-05-31", OPTION_ID,
            times=("07:45", "16:00"), confirmed_by=boss)
    s.daily_life("2026-10-05", "2026-10-30")   # reservations, absences, attendance (until today)
    s.staff_shifts("2026-10-05", "2026-10-30") # shift plans + realtime attendance (until now)
    s.write("payload.json", batch="kalliorinne")
"""
import os
import random
import sys
from datetime import date, datetime, timedelta

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaka_testdata import (Rows, uid, hdt, hm, D, T, add_minutes, date_range, time_range,  # noqa: E402
                            workdays, test_ssn, ascii_email, fake_address, absence_categories,
                            SYSTEM_USER)

DEFAULT_FEATURES = ["MESSAGING", "MOBILE", "RESERVATIONS", "VASU_AND_PEDADOC", "MOBILE_MESSAGING",
                    "PLACEMENT_TERMINATION", "REALTIME_STAFF_ATTENDANCE", "PUSH_NOTIFICATIONS"]
SHIFTS = [("06:30", "14:15"), ("08:00", "15:45"), ("09:45", "17:30")]  # early, middle, late
NO_GROUP_TYPES = ("TRAINING", "OTHER_WORK", "SICKNESS", "CHILD_SICKNESS")


class Obj(dict):
    __getattr__ = dict.__getitem__


class Scenario:
    def __init__(self, commit, today, now="12:00", seed=1, repo=None):
        self.rng = random.Random(seed)
        self.today, self.now = D(today), T(now)
        self.rows = Rows()
        self.categories = absence_categories(commit, repo)
        self.children, self.staff = [], []
        self.absent = {}  # (child_id, date) -> absenceType, filled by absence()/daily_life()

    # -------------------------------------------------------------- unit and staff
    def unit(self, name, area_id, groups, preschool=False, start="2026-08-01", capacity=None,
             address=None, caretakers=3, features=DEFAULT_FEATURES, opening=("06:30", "17:30"), **extra):
        """New unit with groups (list of names). Integrations (Varda, Koski) are off."""
        street, postal = address or (f"{name.split()[-1]}ntie {self.rng.randint(1, 20)}", "02320")
        u = self.rows.add("daycare", **{
            "id": uid(), "name": name, "openingDate": D(start).isoformat(), "areaId": area_id,
            "type": ["CENTRE", "PRESCHOOL"] if preschool else ["CENTRE"],
            "dailyPreschoolTime": time_range("09:00", "13:00") if preschool else None,
            "providerType": "MUNICIPAL", "capacity": capacity or 21 * len(groups), "language": "fi",
            "uploadToVarda": False, "uploadChildrenToVarda": False, "uploadToKoski": False,
            "visitingAddress": {"streetAddress": street, "postalCode": postal, "postOffice": "Espoo"},
            "email": ascii_email("paivakoti", name.split()[-1]), "phone": f"+358 9 816 {self.rng.randrange(10000, 99999)}",
            "operationTimes": [time_range(*opening)] * 5 + [None, None],
            "enabledPilotFeatures": list(features),
            "mealtimeBreakfast": time_range("08:00", "08:30"), "mealtimeLunch": time_range("11:00", "11:45"),
            "mealtimeSnack": time_range("14:00", "14:30"), **extra})
        gids = {}
        for g in groups:
            gids[g] = self.rows.add("daycare_group", id=uid(), daycareId=u["id"], name=g,
                                    startDate=D(start).isoformat(), endDate=None)["id"]
            self.rows.add("daycare_caretaker", id=uid(), groupId=gids[g], amount=caretakers,
                          startDate=D(start).isoformat(), endDate=None)
        return Obj(id=u["id"], name=name, groups=gids)

    def employee(self, first, last, unit, role="STAFF", groups=(), coefficient="7.00", pin=None, **extra):
        """Employee with a unit role, group access and (optional) mobile PIN. coefficient "7.00"
        counts towards staffing, "0.00" doesn't. Shifts are generated for employees with groups."""
        e = self.rows.add("employee", **{"id": uid(), "firstName": first, "lastName": last,
                                         "email": ascii_email(first, last), "roles": [], "active": True,
                                         "employeeNumber": str(self.rng.randrange(100000, 999999)), **extra})
        self.rows.add("daycare_acl", daycareId=unit.id, employeeId=e["id"], role=role)
        gids = [unit.groups[g] for g in groups]
        for g in gids:
            self.rows.add("daycare_group_acl", groupId=g, employeeId=e["id"])
        if pin or role in ("STAFF", "UNIT_SUPERVISOR"):
            self.rows.add("employee_pin", id=uid(), userId=e["id"], pin=pin or f"{self.rng.randrange(1000, 9999)}")
        emp = Obj(id=e["id"], first=first, last=last, groups=gids, coefficient=coefficient, role=role)
        self.staff.append(emp)
        return emp

    # -------------------------------------------------------------- families
    def family(self, guardians, address=None, language="fi", **extra):
        """guardians: [(first, last, dob, "M"/"F"), ...] (1 or 2). Returns the family; the first
        guardian becomes head of family, two guardians are partners."""
        addr = address or fake_address(self.rng)
        ids = []
        for first, last, dob, sex in guardians:
            p = self.rows.add("adult", **{
                "id": uid(), "firstName": first, "lastName": last, "dateOfBirth": D(dob).isoformat(),
                "ssn": test_ssn(dob, sex == "M", self.rng), "email": ascii_email(first, last),
                "verifiedEmail": ascii_email(first, last), "phone": f"+35840{self.rng.randrange(1000000, 9999999)}",
                "language": language, "municipalityOfResidence": "Espoo", **addr, **extra})
            ids.append(p["id"])
        if len(ids) == 2:
            self.rows.add("fridge_partnership", id=uid(), first=ids[0], second=ids[1],
                          startDate=f"{self.rng.randint(2010, 2019)}-06-01", endDate=None)
        return Obj(guardians=ids, address=addr, language=language, last=guardians[0][1])

    def child(self, family, first, dob, sex, last=None, **extra):
        c = self.rows.add("child", **{
            "id": uid(), "firstName": first, "lastName": last or family.last, "dateOfBirth": D(dob).isoformat(),
            "ssn": test_ssn(dob, sex == "M", self.rng), "language": family.language,
            "municipalityOfResidence": "Espoo", **family.address, **extra})
        for g in family.guardians:
            self.rows.add("guardian", guardianId=g, childId=c["id"])
        dob = D(dob)
        self.rows.add("fridge_child", id=uid(), childId=c["id"], headOfChildId=family.guardians[0],
                      startDate=dob.isoformat(), endDate=(dob.replace(year=dob.year + 18) - timedelta(days=1)).isoformat())
        return Obj(id=c["id"], first=first, family=family)

    def place(self, child, unit, group, placement_type, start, end, service_need_option, times=None,
              confirmed_by=None, **extra):
        """Placement + service need + group placement + regular daily times (times=(start, end))."""
        start, end = D(start).isoformat(), D(end).isoformat()
        p = self.rows.add("placement", **{"id": uid(), "type": placement_type, "childId": child.id,
                                          "unitId": unit.id, "startDate": start, "endDate": end, **extra})
        self.rows.add("service_need", id=uid(), placementId=p["id"], startDate=start, endDate=end,
                      optionId=service_need_option, shiftCare="NONE", partWeek=False,
                      confirmedBy=confirmed_by.id if confirmed_by else SYSTEM_USER, confirmedAt=hdt(start, "10:00"))
        self.rows.add("daycare_group_placement", id=uid(), daycarePlacementId=p["id"],
                      daycareGroupId=unit.groups[group], startDate=start, endDate=end)
        preschool_only = placement_type in ("PRESCHOOL", "PREPARATORY")
        times = times or (("08:55", "13:05") if preschool_only else ("08:00", "16:00"))
        if not preschool_only:
            self.rows.add("daily_service_times", id=uid(), childId=child.id, type="REGULAR",
                          validityPeriod=date_range(start), regularTimes=time_range(*times))
        child.update(unit=unit, group=unit.groups[group], type=placement_type, start=D(start), end=D(end),
                     times=times, reservations=not preschool_only)
        self.children.append(child)
        return p["id"]

    # -------------------------------------------------------------- everyday data
    def absence(self, child, start, end, absence_type="OTHER_ABSENCE", by=None, at=None):
        """Absence rows for every workday and every absence category of the child's placement."""
        for d in workdays(start, end):
            self.absent[(child.id, d)] = absence_type
            for cat in self.categories[child.type]:
                self.rows.add("absence", id=uid(), childId=child.id, date=d.isoformat(), absenceType=absence_type,
                              absenceCategory=cat, modifiedBy=by or child.family.guardians[0],
                              modifiedAt=at or hdt(d - timedelta(days=1 if absence_type != "SICKLEAVE" else 0), "07:00"))

    def daily_life(self, start, end, sick_rate=0.04, reserve_ahead=True):
        """For every placed child, on workdays in [start, end] within the placement: random sick
        streaks (SICKLEAVE by a guardian), reservations (also future days) and attendances up to
        today (today: arrived only if before `now`, not departed). Absences you added with
        absence() before calling this are respected."""
        for c in self.children:
            booker = c.family.guardians[self.rng.randrange(len(c.family.guardians))]
            days = [d for d in workdays(max(D(start), c.start), min(D(end), c.end))]
            for d in days:  # sickness streaks, only up to today
                if d <= self.today and (c.id, d) not in self.absent and self.rng.random() < sick_rate:
                    streak = [x for x in days if d <= x <= min(d + timedelta(days=self.rng.randint(0, 2)), self.today)]
                    self.absence(c, streak[0], streak[-1], "SICKLEAVE", by=booker)
            s0, e0 = T(c.times[0]), T(c.times[1])
            for d in days:
                if (c.id, d) in self.absent:
                    continue
                rs, re_ = s0, e0
                if c.reservations:
                    if d.weekday() == 4:
                        re_ = add_minutes(e0, -30)
                    if self.rng.random() < 0.12:
                        rs = add_minutes(rs, self.rng.choice([-15, 15, 30]))
                    if reserve_ahead or d <= self.today:
                        self.rows.add("attendance_reservation", id=uid(), childId=c.id, date=d.isoformat(),
                                      startTime=hm(rs), endTime=hm(re_), createdBy=booker,
                                      createdAt=hdt(d - timedelta(days=self.rng.randint(7, 20)), "20:30"))
                if d > self.today:
                    continue
                arr = add_minutes(rs, self.rng.randint(-10, 12))
                if d == self.today and arr > self.now:
                    continue
                dep = None if d == self.today else add_minutes(re_, self.rng.randint(-25, 8))
                staff = [s.id for s in self.staff if c.group in s.groups] or [SYSTEM_USER]
                self.rows.add("child_attendance", childId=c.id, unitId=c.unit.id, date=d.isoformat(), arrived=hm(arr),
                              departed=hm(dep) if dep else None, modifiedAt=hdt(d, dep or arr),
                              modifiedBy=self.rng.choice(staff))

    def staff_shifts(self, start, end, sick_rate=0.03):
        """Weekly rotating shift plans for employees with groups and realtime attendance up to now.
        Occasional sick days (type SICKNESS, no group). Supervisors (coefficient 0) work 8-16."""
        for i, e in enumerate(self.staff):
            if not e.groups:
                continue
            for d in workdays(start, end):
                if e.coefficient == "0.00":
                    s, t = "08:00", "16:00"
                else:
                    s, t = SHIFTS[(i + d.isocalendar()[1]) % len(SHIFTS)]
                self.rows.add("staff_attendance_plan", id=uid(), employeeId=e.id, type="PRESENT",
                              startTime=hdt(d, s), endTime=hdt(d, t), description=None)
                if d > self.today:
                    continue
                if d < self.today and self.rng.random() < sick_rate:
                    self._realtime(e, d, T(s), T(t), None, "SICKNESS", "0.00")
                    continue
                arr = add_minutes(s, self.rng.randint(-8, 4))
                if d == self.today and arr > self.now:
                    continue
                dep = None if d == self.today and T(t) > self.now else add_minutes(t, self.rng.randint(-4, 10))
                self._realtime(e, d, arr, dep, e.groups[0], "PRESENT", e.coefficient)

    def _realtime(self, e, d, arr, dep, group, typ, coef):
        self.rows.add("staff_attendance_realtime", id=uid(), employeeId=e.id, groupId=group,
                      arrived=hdt(d, arr), departed=hdt(d, dep) if dep else None, occupancyCoefficient=coef,
                      type=typ, departedAutomatically=False, modifiedAt=hdt(d, dep or arr), modifiedBy=e.id)

    # -------------------------------------------------------------- output
    def write(self, path, batch, rollback=False):
        return self.rows.write(path, batch=batch, rollback=rollback)
