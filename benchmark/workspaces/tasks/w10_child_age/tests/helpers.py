from clinic.core.people import Doctor, Patient
from clinic.scheduling.book import Book


def clinic():
    doctors = {"D1": Doctor("D1", "Dr Bello", "general"),
               "D2": Doctor("D2", "Dr Okon", "children", day_start="08:00", day_end="12:00", lunch=("10:00", "10:30"), fee=20000)}
    patients = {"P1": Patient("P1", "Ngozi Eze", "0801", 1990),
                "P2": Patient("P2", "Tayo Ade", "0802", 2015),
                "P3": Patient("P3", "Musa Bala", "0803", 1985, insured=True)}
    return doctors, patients, Book()
