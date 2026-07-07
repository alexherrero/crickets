# NEGATIVE fixture: privacy-pii-in-url should stay silent — an opaque token
# is used instead of the raw email.
def build_password_reset_url(reset_token):
    reset_url = "https://app.example.com/reset?token=" + reset_token
    return reset_url
