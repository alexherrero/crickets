// POSITIVE fixture: privacy-pii-in-client-storage should flag this.
function rememberUser(userEmail) {
    localStorage.setItem("user_email", userEmail);
}
