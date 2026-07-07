# POSITIVE fixture: privacy-pii-to-third-party-sink should flag this — a raw
# email is forwarded to a third-party analytics SDK call.
def track_signup(user_email):
    analytics.track("signup", {"email": user_email, "plan": "free"})
