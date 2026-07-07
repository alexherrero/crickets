# POSITIVE fixture: privacy-pii-in-url should flag this.
def build_password_reset_url(user_email):
    reset_url = "https://app.example.com/reset?email=" + user_email
    return reset_url
