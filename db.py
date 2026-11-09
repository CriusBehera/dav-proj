"""Database helpers: connection, password hashing, users and notes."""
import hashlib
import hmac
import os
import re

import mysql.connector
import streamlit as st


MAX_ATTEMPTS = 5   # wrong passwords before the account is locked
LOCK_MINUTES = 5


def get_connection():
    """Open a MySQL connection using settings from .streamlit/secrets.toml."""
    cfg = st.secrets["mysql"]
    options = dict(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        use_pure=True,  # pure-Python driver still supports TiDB's mysql_native_password login
    )
    if cfg.get("ssl_ca"):  # cloud databases need an encrypted (TLS) connection
        options.update(ssl_ca=cfg["ssl_ca"], ssl_verify_cert=True)
    return mysql.connector.connect(**options)


def run_query(sql, params=(), fetch=False):
    """Run one SQL statement. Returns rows (as dicts) when fetch=True."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ---------- Passwords (never store plain text) ----------

def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + digest.hex()


def check_password(password, stored):
    salt_hex, digest_hex = stored.split(":")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- Users ----------

PUBLIC_USER = ("id, username, login_email, provider, created_at, "
               "password_hash IS NOT NULL AS has_password, totp_secret IS NOT NULL AS has_totp")


def get_user(field, value):
    """One user by id, username or login_email, without the password hash."""
    assert field in ("id", "username", "login_email")
    rows = run_query(f"SELECT {PUBLIC_USER} FROM users WHERE {field} = %s", (value,), fetch=True)
    return rows[0] if rows else None


def create_user(username, email, password):
    """Create a username + email + password account. Returns None or an error message."""
    email = email.strip().lower()
    if get_user("username", username):
        return "That username is already taken."
    if get_user("login_email", email):
        return "That email already has an account. Sign in, or use Continue with Google."
    try:
        run_query(
            "INSERT INTO users (username, login_email, password_hash) VALUES (%s, %s, %s)",
            (username, email, hash_password(password)),
        )
        return None
    except mysql.connector.IntegrityError:  # someone took it a moment ago
        return "That username or email is already taken."


def authenticate(identifier, password):
    """Check a username-or-email + password login.

    Returns (user, None) on success or (None, error message). After
    MAX_ATTEMPTS wrong passwords in a row the account is locked for
    LOCK_MINUTES, so nobody can keep guessing passwords.
    """
    identifier = identifier.strip()
    field = "login_email" if "@" in identifier else "username"
    rows = run_query(
        "SELECT id, password_hash, failed_attempts, "
        "TIMESTAMPDIFF(SECOND, NOW(), locked_until) AS locked_for "
        f"FROM users WHERE {field} = %s",
        (identifier.lower() if field == "login_email" else identifier,),
        fetch=True,
    )
    if not rows:
        return None, "Wrong username, email or password."
    row = rows[0]

    if row["password_hash"] is None:
        return None, "This account signs in with Google. Use “Continue with Google”."
    if row["locked_for"] and row["locked_for"] > 0:
        minutes = -(-row["locked_for"] // 60)  # round up
        return None, f"Too many wrong passwords. Account locked — try again in {minutes} min."

    if not check_password(password, row["password_hash"]):
        attempts = row["failed_attempts"] + 1
        if attempts >= MAX_ATTEMPTS:
            run_query(
                "UPDATE users SET failed_attempts = 0, "
                "locked_until = NOW() + INTERVAL %s MINUTE WHERE id = %s",
                (LOCK_MINUTES, row["id"]),
            )
            return None, f"Too many wrong passwords. Account locked for {LOCK_MINUTES} minutes."
        run_query("UPDATE users SET failed_attempts = %s WHERE id = %s", (attempts, row["id"]))
        left = MAX_ATTEMPTS - attempts
        return None, f"Wrong username, email or password. {left} attempt(s) left before lock."

    # Counters are cleared only after the whole sign-in (including the authenticator code)
    # succeeds, so wrong codes can't be reset by re-entering the password.
    return get_user("id", row["id"]), None


def locked_minutes(user_id):
    """Minutes left on a lock (0 when the account is not locked)."""
    rows = run_query("SELECT TIMESTAMPDIFF(SECOND, NOW(), locked_until) AS s FROM users WHERE id = %s",
                     (user_id,), fetch=True)
    seconds = (rows[0]["s"] or 0) if rows else 0
    return -(-seconds // 60) if seconds > 0 else 0


def register_failure(user_id):
    """Count one wrong authenticator code; locks the account like wrong passwords do.

    Returns True when this failure locked the account.
    """
    rows = run_query("SELECT failed_attempts FROM users WHERE id = %s", (user_id,), fetch=True)
    attempts = (rows[0]["failed_attempts"] if rows else 0) + 1
    if attempts >= MAX_ATTEMPTS:
        run_query("UPDATE users SET failed_attempts = 0, locked_until = NOW() + INTERVAL %s MINUTE "
                  "WHERE id = %s", (LOCK_MINUTES, user_id))
        return True
    run_query("UPDATE users SET failed_attempts = %s WHERE id = %s", (attempts, user_id))
    return False


def clear_attempts(user_id):
    run_query("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = %s", (user_id,))


def google_user(email, name=""):
    """Find the account for a Google-verified email, or create one.

    An existing username/password account with the same email is reused, so
    both ways of signing in lead to the same account.
    """
    email = email.strip().lower()
    user = get_user("login_email", email)
    if user:
        return user
    base = re.sub(r"[^A-Za-z0-9_]", "", (name or email.split("@")[0]).replace(" ", "_"))[:16]
    base = base if len(base) >= 3 else (base + "user")[:16]
    username, n = base, 1
    while get_user("username", username):
        n += 1
        username = f"{base}{n}"
    run_query("INSERT INTO users (username, login_email, provider) VALUES (%s, %s, 'google')",
              (username, email))
    return get_user("login_email", email)


def change_password(user_id, current, new):
    """Returns True if the current password was right and the new one is saved."""
    rows = run_query("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch=True)
    if not rows or not rows[0]["password_hash"] or not check_password(current, rows[0]["password_hash"]):
        return False
    run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new), user_id))
    return True


def set_first_password(user_id, new):
    """Give a Google-only account a password (only if it has none yet)."""
    return run_query("UPDATE users SET password_hash = %s WHERE id = %s AND password_hash IS NULL",
                     (hash_password(new), user_id)) == 1


def add_login_email(user_id, email):
    """Attach an email to an older account that has none. Returns None or an error message."""
    email = email.strip().lower()
    if get_user("login_email", email):
        return "That email is already used by another account."
    run_query("UPDATE users SET login_email = %s WHERE id = %s AND login_email IS NULL",
              (email, user_id))
    return None


def get_totp_secret(user_id):
    rows = run_query("SELECT totp_secret FROM users WHERE id = %s", (user_id,), fetch=True)
    return rows[0]["totp_secret"] if rows else None


def save_totp(user_id, secret, backup_codes):
    """Store the authenticator secret and the (hashed) one-time backup codes."""
    hashed = ",".join(hashlib.sha256(c.encode()).hexdigest() for c in backup_codes)
    run_query("UPDATE users SET totp_secret = %s, backup_codes = %s WHERE id = %s",
              (secret, hashed, user_id))


def use_backup_code(user_id, code):
    """True (and the code is burnt) if `code` is an unused backup code."""
    rows = run_query("SELECT backup_codes FROM users WHERE id = %s", (user_id,), fetch=True)
    codes = (rows[0]["backup_codes"] or "").split(",") if rows else []
    digest = hashlib.sha256(code.strip().lower().encode()).hexdigest()
    if digest not in codes:
        return False
    codes.remove(digest)
    run_query("UPDATE users SET backup_codes = %s WHERE id = %s", (",".join(codes), user_id))
    return True


def system_info():
    """MySQL version and row counts for the DAV Project home screen."""
    return run_query(
        "SELECT VERSION() AS version, DATABASE() AS db, "
        "(SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM notes) AS notes",
        fetch=True,
    )[0]


# ---------- Notes (the example app: create / read / delete) ----------

def add_note(title, body, user_id):
    run_query("INSERT INTO notes (title, body, user_id) VALUES (%s, %s, %s)", (title, body, user_id))


def get_notes(search=""):
    return run_query(
        "SELECT n.id, n.title, n.body, u.username AS author, n.created_at "
        "FROM notes n LEFT JOIN users u ON u.id = n.user_id "
        "WHERE n.title LIKE %s OR n.body LIKE %s ORDER BY n.created_at DESC",
        (f"%{search}%", f"%{search}%"), fetch=True)


def delete_note(note_id):
    run_query("DELETE FROM notes WHERE id = %s", (note_id,))


# ---------- SQL playground ----------

# Words that change data or files. Blocked in the playground because some
# MySQL-compatible clouds (e.g. TiDB) don't enforce READ ONLY transactions.
WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|replace|drop|alter|truncate|create|rename|grant|revoke|"
    r"load|lock|unlock|call|handler|set|into)\b",
    re.IGNORECASE,
)


def run_select(sql):
    """Run a read-only query typed by the user. Returns (columns, rows)."""
    sql = sql.strip().rstrip(";").strip()
    if not sql.lower().startswith(("select", "with", "show", "describe")):
        raise ValueError("Only SELECT, WITH, SHOW and DESCRIBE queries are allowed here.")
    if ";" in sql:
        raise ValueError("Run one query at a time (only one ; at the end).")
    word = WRITE_WORDS.search(sql)
    if word:
        raise ValueError(f"“{word.group(0).upper()}” changes data, so it isn't allowed here.")
    if any(w in sql.lower() for w in ("password_hash", "login_email", "totp_secret", "backup_codes")):
        raise ValueError("Password hashes and sign-in emails are private, so they can't be queried.")
    conn = get_connection()
    try:
        try:
            conn.start_transaction(readonly=True)  # on real MySQL this also blocks writes
        except mysql.connector.Error:
            # TiDB rejects READ ONLY by default ("noop function"). The keyword
            # checks above and the rollback below still keep the data safe.
            conn.start_transaction()
        cur = conn.cursor()
        cur.execute(sql)
        columns, rows = list(cur.column_names), cur.fetchall()
        # SELECT * FROM users would still include those columns, so drop them
        hidden = [i for i, c in enumerate(columns) if c.lower() in ("password_hash", "login_email", "totp_secret", "backup_codes")]
        for i in reversed(hidden):
            del columns[i]
            rows = [row[:i] + row[i + 1:] for row in rows]
        return columns, rows
    finally:
        conn.rollback()  # make sure nothing is ever saved from this box
        conn.close()
