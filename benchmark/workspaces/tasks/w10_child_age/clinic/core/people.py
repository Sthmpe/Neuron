"""Patients and doctors."""
from dataclasses import dataclass, field


@dataclass
class Patient:
    number: str
    name: str
    phone: str
    birth_year: int
    insured: bool = False
    notes: list = field(default_factory=list)

    def age_in(self, year):
        return year - self.birth_year

    def is_child(self, year):
        return self.age_in(year) <= 16


@dataclass
class Doctor:
    code: str
    name: str
    speciality: str
    day_start: str = "09:00"
    day_end: str = "17:00"
    lunch: tuple = ("13:00", "14:00")
    fee: int = 15000      # naira per visit
