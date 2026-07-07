// NEGATIVE fixture: privacy-pii-in-client-storage should stay silent — an
// opaque session token is stored, not PII.
function rememberSession(sessionToken) {
    localStorage.setItem("session_token", sessionToken);
}
