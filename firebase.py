"""Email verification through Firebase Authentication (REST API, no SDK needed).

Firebase keeps a second copy of each email + password account. Its only job is to
email the verification link and say whether the address has been confirmed.
Google sign-in does not use this (Google already verifies the address).
"""
import requests
import streamlit as st

URL = "https://identitytoolkit.googleapis.com/v1/accounts:"

NICE = {
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many requests. Please wait a few minutes and try again.",
    "OPERATION_NOT_ALLOWED": "Email/Password sign-in is not turned on in your Firebase project.",
    "INVALID_PASSWORD": "Your password doesn't match the one stored for email verification.",
}


def _key():
    try:
        return st.secrets["firebase"]["api_key"]
    except (KeyError, FileNotFoundError):
        return None


def ready():
    return bool(_key())


def web_config():
    """Public Firebase web settings for the browser-side Google button, or None."""
    try:
        cfg = st.secrets["firebase"]
        return {"apiKey": cfg["api_key"], "authDomain": cfg["auth_domain"],
                "projectId": cfg.get("project_id", "")}
    except (KeyError, FileNotFoundError):
        return None


def google_profile(id_token):
    """Verify a Firebase ID token (from the Google pop-up) with Firebase itself.

    Returns ({"email", "name"}, None) or (None, error message). Only Google
    accounts with a verified email are accepted.
    """
    info, error = _call("lookup", {"idToken": id_token})
    if error:
        return None, "Google sign-in could not be verified. Please try again."
    user = info["users"][0]
    providers = [p.get("providerId") for p in user.get("providerUserInfo", [])]
    if "google.com" not in providers or not user.get("email") or not user.get("emailVerified"):
        return None, "That Google account has no verified email."
    return {"email": user["email"].lower(), "name": user.get("displayName", "")}, None


def _call(action, payload):
    """POST to Firebase. Returns (data, None) or (None, error code)."""
    try:
        r = requests.post(URL + action, params={"key": _key()}, json=payload, timeout=15)
        data = r.json()
    except (requests.RequestException, ValueError):
        return None, "NETWORK_ERROR"
    if r.ok:
        return data, None
    return None, data.get("error", {}).get("message", "UNKNOWN").split(" ")[0]


def explain(code):
    return NICE.get(code, f"Firebase error: {code}")


def send_verification(token):
    return _call("sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": token})[1]


def register(email, password):
    """Create the Firebase copy and email the link. Returns an error code or None."""
    data, error = _call("signUp", {"email": email, "password": password, "returnSecureToken": True})
    if error:
        return None if error == "EMAIL_EXISTS" else error
    return send_verification(data["idToken"])


def check(email, password, resend=False):
    """Returns ('verified' | 'unverified' | 'error', error code or None).

    Accounts that don't exist in Firebase yet (made before this feature) are
    created on the spot. An unverified account gets a fresh link when `resend`.
    """
    data, error = _call("signInWithPassword",
                        {"email": email, "password": password, "returnSecureToken": True})
    if error in ("EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS"):
        # Firebase hides which one it is: try creating the account; if it exists, the password differs
        data, up_error = _call("signUp", {"email": email, "password": password,
                                          "returnSecureToken": True})
        if up_error == "EMAIL_EXISTS":
            return "error", "INVALID_PASSWORD"
        if up_error:
            return "error", up_error
        error = send_verification(data["idToken"])
        return ("unverified", None) if not error else ("error", error)
    if error:
        return "error", error
    info, error = _call("lookup", {"idToken": data["idToken"]})
    if error:
        return "error", error
    if info["users"][0].get("emailVerified"):
        return "verified", None
    if resend:
        error = send_verification(data["idToken"])
        if error:
            return "error", error
    return "unverified", None


def change_password(email, old, new):
    """Keep Firebase's copy of the password in step. Best effort."""
    data, error = _call("signInWithPassword",
                        {"email": email, "password": old, "returnSecureToken": True})
    if not error:
        _call("update", {"idToken": data["idToken"], "password": new, "returnSecureToken": False})
