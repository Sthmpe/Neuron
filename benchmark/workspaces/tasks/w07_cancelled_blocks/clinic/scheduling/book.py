"""The appointment book."""
from dataclasses import dataclass

from ..core.times import overlaps, to_minutes
from .slots import day_slots


class Clash(Exception):
    pass


@dataclass
class Appointment:
    ref: str
    patient: str
    doctor: str
    date: str
    start: str
    minutes: int = 30
    status: str = "booked"     # booked, attended, missed, cancelled


class Book:
    def __init__(self):
        self.appointments = []
        self._n = 0

    def for_doctor(self, doctor_code, date):
        return [a for a in self.appointments
                if a.doctor == doctor_code and a.date == date]

    def book(self, patient, doctor, date, start, minutes=30):
        if start not in day_slots(doctor, 30):
            raise ValueError(f"{start} is not a slot for {doctor.name}")
        s = to_minutes(start)
        for a in self.for_doctor(doctor.code, date):
            if overlaps(s, s + minutes, to_minutes(a.start), to_minutes(a.start) + a.minutes):
                raise Clash(f"{doctor.name} is busy at {a.start}")
        for a in self.appointments:     # a patient cannot be in two places at once
            if a.patient == patient.number and a.date == date and a.status == "booked" and \
                    overlaps(s, s + minutes, to_minutes(a.start), to_minutes(a.start) + a.minutes):
                raise Clash(f"{patient.name} already has an appointment at {a.start}")
        self._n += 1
        appt = Appointment(f"A{self._n:04d}", patient.number, doctor.code, date, start, minutes)
        self.appointments.append(appt)
        return appt

    def cancel(self, ref):
        for a in self.appointments:
            if a.ref == ref:
                a.status = "cancelled"
                return a
        raise KeyError(ref)

    def mark(self, ref, status):
        if status not in ("attended", "missed"):
            raise ValueError(status)
        for a in self.appointments:
            if a.ref == ref:
                a.status = status
                return a
        raise KeyError(ref)
