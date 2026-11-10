import requests
import streamlit as st

URL = "https://identitytoolkit.googleapis.com/v1/accounts:"

NICE = {
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many tries. Please wait a few minutes.",
    "INVALID_PASSWORD": "Wrong password.",
}


def _key():
    try:
        return st.secrets["firebase"]["api_key"]
    except (KeyError, FileNotFoundError):
        return None


def ready():
    return bool(_key())


def web_config():
    try:
        cfg = st.secrets["firebase"]
        return {"apiKey": cfg["api_key"], "authDomain": cfg["auth_domain"],
                "projectId": cfg.get("project_id", "")}
    except (KeyError, FileNotFoundError):
        return None


def google_profile(id_token):
    info, error = _call("lookup", {"idToken": id_token})
    if error:
        return None, "An error occurred. Please try again."
    user = info["users"][0]
    providers = [p.get("providerId") for p in user.get("providerUserInfo", [])]
    if "google.com" not in providers or not user.get("email") or not user.get("emailVerified"):
        return None, "That Google account has no verified email."
    return {"email": user["email"].lower(), "name": user.get("displayName", "")}, None


def _call(action, payload):
    try:
        r = requests.post(URL + action, params={"key": _key()}, json=payload, timeout=15)
        data = r.json()
    except (requests.RequestException, ValueError):
        return None, "NETWORK_ERROR"
    if r.ok:
        return data, None
    return None, data.get("error", {}).get("message", "UNKNOWN").split(" ")[0]


def explain(code):
    return NICE.get(code, "An error occurred. Please try again.")


def send_verification(token):
    return _call("sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": token})[1]


def register(email, password):
    data, error = _call("signUp", {"email": email, "password": password, "returnSecureToken": True})
    if error:
        return None if error == "EMAIL_EXISTS" else error
    return send_verification(data["idToken"])


def check(email, password, resend=False):
    data, error = _call("signInWithPassword",
                        {"email": email, "password": password, "returnSecureToken": True})
    if error in ("EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS"):
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
    data, error = _call("signInWithPassword",
                        {"email": email, "password": old, "returnSecureToken": True})
    if not error:
        _call("update", {"idToken": data["idToken"], "password": new, "returnSecureToken": False})
