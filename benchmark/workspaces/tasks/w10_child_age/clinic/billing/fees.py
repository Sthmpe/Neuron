"""What a visit costs the patient."""

CHILD_DISCOUNT = 50          # percent off for under-16s
INSURANCE_SHARE = 80         # percent the insurer pays
MISSED_FEE_SHARE = 50        # percent of the fee charged for a missed visit


def visit_fee(doctor, patient, year):
    fee = doctor.fee
    if patient.is_child(year):
        fee = fee * (100 - CHILD_DISCOUNT) // 100
    return fee


def patient_pays(doctor, patient, year):
    """After the insurer's share, if insured."""
    fee = visit_fee(doctor, patient, year)
    if patient.insured:
        return fee - fee * INSURANCE_SHARE // 100
    return fee


def bill(book, patients, doctors, year):
    """{patient number: amount owed} for attended and missed appointments."""
    owed = {}
    for a in book.appointments:
        if a.status not in ("attended", "missed"):
            continue
        p, d = patients[a.patient], doctors[a.doctor]
        amount = patient_pays(d, p, year)
        if a.status == "missed":
            amount = amount * MISSED_FEE_SHARE // 100
        owed[p.number] = owed.get(p.number, 0) + amount
    return owed
