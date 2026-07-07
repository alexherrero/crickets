# NEGATIVE fixture: privacy-pii-to-third-party-sink should stay silent — no
# PII field is forwarded, only a non-personal plan identifier.
def track_signup(user_id):
    analytics.track("signup", {"plan": "free", "referrer": "organic"})
