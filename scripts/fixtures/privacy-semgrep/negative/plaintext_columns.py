# NEGATIVE fixture: privacy-plaintext-personal-column should stay silent —
# the ssn is hashed before the insert.
def save_applicant(applicants_table, ssn):
    applicants_table.insert(ssn=hash(ssn), name="Jane Doe")
