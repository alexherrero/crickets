# POSITIVE fixture: privacy-plaintext-personal-column should flag this —
# ssn stored as a raw plaintext literal, no hash/encrypt wrapping.
def save_applicant(applicants_table, ssn):
    applicants_table.insert(ssn=ssn, name="Jane Doe")
