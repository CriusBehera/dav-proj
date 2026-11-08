"""Sign in (username, email or Google), create account, account page, password rules."""
import re
import secrets

import pyotp
import segno
import streamlit as st

import db
import firebase
import ui

# Passwords containing any of these are among the first an attacker would try
COMMON_PARTS = (
    "password", "passw0rd", "qwerty", "123456", "654321", "abcdef", "abc123", "admin",
    "welcome", "letmein", "iloveyou", "football", "monkey", "sunshine", "princess", "dragon",
)
USERNAME_RULE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL_RULE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def password_checks(password, username=""):
    """Every rule a password must pass, as (passed, description) pairs."""
    lowered = password.lower()
    return [
        (len(password) >= 8, "At least 8 characters"),
        (bool(re.search(r"[A-Z]", password)), "An uppercase letter (A–Z)"),
        (bool(re.search(r"[a-z]", password)), "A lowercase letter (a–z)"),
        (bool(re.search(r"\d", password)), "A number (0–9)"),
        (bool(re.search(r"[^A-Za-z0-9]", password)), "A symbol (! @ # $ % …)"),
        (" " not in password, "No spaces"),
        (not username or username.lower() not in lowered, "Doesn't contain your username"),
        (not any(part in lowered for part in COMMON_PARTS), "No common words like “password”"),
    ]


def strength(checks):
    """0–100 score and a label, from how many rules pass."""
    passed = sum(ok for ok, _ in checks)
    score = round(100 * passed / len(checks))
    label = "Weak" if score < 60 else "Okay" if score < 100 else "Strong"
    return score, label


def show_checklist(checks):
    score, label = strength(checks)
    st.progress(score, text=f"Password strength: **{label}**")
    left, right = st.columns(2)
    for n, (ok, text) in enumerate(checks):
        (left if n % 2 == 0 else right).markdown(
            f":{'green' if ok else 'gray'}[{'✓' if ok else '○'} {text}]")


def new_password_inputs(username, key):
    """Password + confirm boxes with the live checklist. Returns the password if valid."""
    password = st.text_input("Password", type="password", key=f"{key}_pw",
                             placeholder="Make it strong")
    confirm = st.text_input("Confirm password", type="password", key=f"{key}_confirm")
    checks = password_checks(password, username)
    if password:
        checks.append((password == confirm, "Both passwords match"))
        show_checklist(checks)
    return password if password and all(ok for ok, _ in checks) else None


AUTH_PANEL = f"""
<div class='auth-panel'>
  <div>
    <div class='sb-brand' style='padding:0'><div class='sb-logo'>DP</div>
      <div><b>DAV Project</b><small>Starter · Streamlit + MySQL</small></div></div>
    <h1>Your data,<br><span>one place.</span></h1>
    <p class='lead'>One sign-in, your apps, and an AI that can read and explain your database.</p>
    <div class='feature'><div class='fi'>📝</div><div><b>Notes</b>
      <small>An example app with a MySQL table you can copy</small></div></div>
    <div class='feature'><div class='fi'>✨</div><div><b>Nuera Core AI</b>
      <small>Ask questions in plain English, get answers from your data</small></div></div>
  </div>
  <div class='auth-foot'>{ui.CREDITS}</div>
</div>
"""


GOOGLE_JS = """
const SDK = "https://www.gstatic.com/firebasejs/10.14.1/";
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  const button = parentElement.querySelector("button");
  const note = parentElement.querySelector(".note");
  button.onclick = async () => {
    const say = (t, bad) => { note.style.color = bad ? "#DC2626" : "#6B7280"; note.textContent = t; console.log("[google]", t); };
    say("Loading Firebase…");
    button.disabled = true;
    try {
      const { initializeApp, getApps } = await import(SDK + "firebase-app.js");
      const { getAuth, GoogleAuthProvider, signInWithPopup, signOut } =
        await import(SDK + "firebase-auth.js");
      const app = getApps().length ? getApps()[0] : initializeApp(data);
      const auth = getAuth(app);
      say("Choose your Google account in the pop-up…");
      const result = await signInWithPopup(auth, new GoogleAuthProvider());
      say("Signed in with Google, checking with the server…");
      const token = await result.user.getIdToken();
      setTriggerValue("token", token);
      signOut(auth).catch(() => {});  // our app keeps the session, Firebase only vouches once
    } catch (e) {
      say(e.code === "auth/popup-closed-by-user" ? "Pop-up closed before finishing." :
          (e.code || "error") + ": " + (e.message || ""), true);
    }
    button.disabled = false;
  };
}
"""

GOOGLE_HTML = """
<button type="button"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.7 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6.1C12.3 13.6 17.6 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.6z"/><path fill="#FBBC05" d="M10.4 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.8-6.1z"/><path fill="#34A853" d="M24 48c6.2 0 11.4-2 15.2-5.5l-7.6-5.9c-2.1 1.4-4.8 2.3-7.6 2.3-6.4 0-11.7-4.1-13.6-9.8l-7.8 6.1C6.5 42.6 14.6 48 24 48z"/></svg>
Continue with Google</button><div class="note"></div>
"""

GOOGLE_CSS = """
button { width: 100%; display: flex; gap: .6rem; align-items: center; justify-content: center;
  padding: .55rem 1rem; border-radius: .6rem; border: 1px solid rgba(128,128,128,.4);
  background: var(--st-secondary-background-color, #fff); color: var(--st-text-color, #111);
  font: inherit; font-weight: 500; cursor: pointer; }
button:hover { border-color: #6366F1; }
button:disabled { opacity: .6; cursor: wait; }
.note { color: #DC2626; font-size: .8rem; margin-top: .3rem; }
"""

google_button = st.components.v2.component("firebase_google", html=GOOGLE_HTML,
                                           css=GOOGLE_CSS, js=GOOGLE_JS)


def google_ready():
    """True when [firebase] has the web settings (api_key and auth_domain)."""
    return firebase.web_config() is not None


def google_sign_in():
    """Show the Firebase Google button; a verified Google sign-in becomes a session."""
    result = google_button(data=firebase.web_config(), key="google_btn",
                           on_token_change=lambda: None)
    if result.token:
        profile, error = firebase.google_profile(result.token)
        if error:
            st.error(error)
            return
        user = db.google_user(profile["email"], profile["name"])
        st.session_state.user = user
        ui.flash(f"Signed in with Google as {user['username']}", "👋")
        st.rerun()


def qr_image(secret, username):
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="DAV Project")
    return segno.make(uri).svg_data_uri(scale=5, border=2)


def totp_setup(user):
    """Mandatory authenticator setup: QR code, backup codes, first-code check."""
    state = st.session_state
    if "totp_new" not in state:
        state.totp_new = (pyotp.random_base32(), [secrets.token_hex(4) for _ in range(8)])
    secret, backups = state.totp_new
    st.markdown("**1.** Install **Microsoft Authenticator** (recommended; Google Authenticator and Authy "
                "also work) and scan this code.")
    st.markdown(f"<img src='{qr_image(secret, user['username'])}' width='170'>", unsafe_allow_html=True)
    st.caption(f"Can't scan? Choose “enter code manually” and use this key: `{secret}`")
    st.markdown("**2.** Save these one-time backup codes. Each works once if you lose your phone.")
    st.code("  ".join(backups))
    with st.form("totp_setup", border=False):
        code = st.text_input("**3.** Enter the 6-digit code shown in the app", max_chars=6)
        if st.form_submit_button("Turn on and continue", type="primary", width="stretch"):
            if pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
                db.save_totp(user["id"], secret, backups)
                state.pop("totp_new", None)
                return True
            st.error("That code is wrong. Check the app and try again.")
    return False


def mask(email):
    name, _, domain = email.partition("@")
    return f"{name[:1]}{'*' * max(len(name) - 1, 2)}@{domain}"


def login_body():
    """Password check first, then the email must be verified (link from Firebase)."""
    state = st.session_state
    pending = state.get("pending")  # {"user": ..., "password": ...} after the password was right
    if not pending:
        with st.form("login", border=False):
            who = st.text_input("Username or email", placeholder="you@example.com or username")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                user, error = db.authenticate(who, password)
                if not user:
                    st.error(error)
                elif not firebase.ready():
                    st.error("Email verification isn't set up yet (add [firebase] to the secrets).")
                else:
                    state.pending = {"user": user, "password": password, "resend": True}
                    st.rerun()
        st.caption(f"🔒 {db.MAX_ATTEMPTS} wrong passwords lock the account for "
                   f"{db.LOCK_MINUTES} minutes. Sign-in needs a verified email and an authenticator code.")
        return

    user = pending["user"]
    if pending.get("email_ok"):
        def done():
            state.pop("pending", None)
            state.user = db.get_user("id", user["id"])
            ui.flash(f"Welcome back, {user['username']}!", "👋")
            st.rerun()

        if not user["has_totp"]:
            st.warning("Two-step sign-in is required. Set up your authenticator app to continue.")
            if totp_setup(user):
                done()
        else:
            st.info("🔐 Open your authenticator app and enter the 6-digit code for DAV Project.")
            with st.form("totp", border=False):
                code = st.text_input("Authenticator code", max_chars=8, placeholder="123456",
                                     help="The 6-digit code, or an unused backup code.")
                if st.form_submit_button("Verify", type="primary", width="stretch"):
                    code = code.strip()
                    secret = db.get_totp_secret(user["id"])
                    if pyotp.TOTP(secret).verify(code, valid_window=1) or db.use_backup_code(user["id"], code):
                        done()
                    pending["tries"] = pending.get("tries", 0) + 1
                    if pending["tries"] >= db.MAX_ATTEMPTS:
                        state.pop("pending", None)
                        ui.flash("Too many wrong codes. Sign in again.", "🔒")
                        st.rerun()
                    st.error(f"Wrong code. {db.MAX_ATTEMPTS - pending['tries']} attempt(s) left.")
    elif not user["login_email"]:
        st.warning("Your account needs a verified email. Add yours and we'll send a link.")
        email = st.text_input("Email", key="pending_email", placeholder="you@example.com").strip()
        if st.button("Send verification link", type="primary", width="stretch",
                     disabled=not EMAIL_RULE.match(email)):
            error = db.add_login_email(user["id"], email)
            if error:
                st.error(error)
            else:
                pending["user"] = db.get_user("id", user["id"])
                st.rerun()
    else:
        status, error = firebase.check(user["login_email"], pending["password"], pending["resend"])
        pending["resend"] = False
        if status == "verified":
            pending["email_ok"] = True
            st.rerun()
        elif status == "error":
            st.error(firebase.explain(error))
        else:
            st.info(f"📧 Verify your email: we sent a link to **{mask(user['login_email'])}**. "
                    "Click it (check spam too), then press the button below.")
            if st.button("I've verified my email", type="primary", width="stretch"):
                st.rerun()
            if st.button("Resend link", width="stretch"):
                pending["resend"] = True
                st.rerun()
    if st.button("Cancel", key="pending_cancel", width="stretch"):
        state.pop("pending", None)
        st.rerun()


def sign_in_page():
    left, gap, right = st.columns([1.1, 0.12, 1])
    left.markdown(AUTH_PANEL, unsafe_allow_html=True)
    with right:
        st.markdown("<div class='auth-head'><h2>Welcome 👋</h2>"
                    "<p>Sign in with Google, your email or your username.</p></div>",
                    unsafe_allow_html=True)
        with ui.card("auth"):
            if google_ready():
                google_sign_in()
            else:
                st.button("Continue with Google", icon=":material/account_circle:",
                          width="stretch", disabled=True, key="google_btn",
                          help="Add the [firebase] web settings to secrets.toml to turn this on.")
            st.markdown("<div class='or'><span>or</span></div>", unsafe_allow_html=True)

            login_tab, register_tab = st.tabs(["Sign in", "Create account"])

            with login_tab:
                login_body()

            with register_tab:
                username = st.text_input("Username", key="reg_user",
                                         placeholder="3–20 letters, numbers or _").strip()
                if username and not USERNAME_RULE.match(username):
                    st.error("Usernames are 3–20 characters: letters, numbers and _ only.")
                email = st.text_input("Email", key="reg_email", placeholder="you@example.com").strip()
                if email and not EMAIL_RULE.match(email):
                    st.error("That doesn't look like an email address.")
                password = new_password_inputs(username, "reg")
                ready = (bool(password) and bool(USERNAME_RULE.match(username))
                         and bool(EMAIL_RULE.match(email)))
                if st.button("Create account", type="primary", width="stretch",
                             disabled=not ready):
                    error = db.create_user(username, email, password)
                    if error:
                        st.error(error)
                    else:
                        sent = firebase.ready() and not firebase.register(email.lower(), password)
                        st.success("Account created! " + (
                            "We emailed you a verification link. Click it, then switch to **Sign in**."
                            if sent else "Switch to **Sign in**."))


def account_page():
    user = st.session_state.user
    ui.page_header("Account", "Your profile, sign-in methods and password.", "os", "👤")
    left, right = st.columns([1, 1.6])
    with left, ui.card():
        st.subheader("Profile", anchor=False)
        email = user.get("login_email")
        st.markdown(f"<div class='profile'><div class='avatar'>{user['username'][0].upper()}</div>"
                    f"<div><b>{user['username']}</b><small>{email or 'No email yet'}<br>Member since "
                    f"{user['created_at']:%d %B %Y}</small></div></div>", unsafe_allow_html=True)
        methods = [m for m, on in (("Password", user["has_password"]),
                                   ("Google", bool(email) and google_ready())) if on]
        ui.stats([("Sign in with", " + ".join(methods) or "—"), ("Lockout", f"{db.MAX_ATTEMPTS} tries")])

    with right:
        if not email:
            with ui.card("add_email"):
                st.subheader("Add your email", anchor=False)
                st.caption("Lets you sign in with your email, and with Google using the same address.")
                new_email = st.text_input("Email", key="add_email_box", placeholder="you@example.com")
                if st.button("Save email", type="primary",
                             disabled=not EMAIL_RULE.match(new_email.strip())):
                    error = db.add_login_email(user["id"], new_email)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.user = db.get_user("id", user["id"])
                        ui.flash("Email saved", "📧")
                        st.rerun()

        if user["has_password"]:
            with ui.card("totp"):
                st.subheader("Two-step sign-in", anchor=False)
                st.success("On (required). Every password sign-in asks for a code from your authenticator app.")

        with ui.card("password"):
            has_password = user["has_password"]
            st.subheader("Change password" if has_password else "Set a password", anchor=False)
            if not has_password:
                st.caption("You signed in with Google. Add a password to also sign in with your "
                           "username or email.")
            current = st.text_input("Current password", type="password", key="cur_pw") if has_password else None
            new = new_password_inputs(user["username"], "chg")
            ready = bool(new) and (bool(current) or not has_password)
            if st.button("Update password" if has_password else "Set password", type="primary",
                         disabled=not ready):
                done = (db.change_password(user["id"], current, new) if has_password
                        else db.set_first_password(user["id"], new))
                if done:
                    if has_password and user["login_email"] and firebase.ready():
                        firebase.change_password(user["login_email"], current, new)
                    for k in ("cur_pw", "chg_pw", "chg_confirm"):
                        st.session_state.pop(k, None)
                    st.session_state.user = db.get_user("id", user["id"])
                    ui.flash("Password saved", "🔑")
                    st.rerun()
                else:
                    st.error("Your current password is wrong.")
