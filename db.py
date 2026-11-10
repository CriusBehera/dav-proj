import hashlib
import hmac
import os
import re

import mysql.connector
import streamlit as st


MAX_ATTEMPTS = 5
LOCK_MINUTES = 5


def get_connection():
    cfg = st.secrets["mysql"]
    options = dict(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        use_pure=True,
    )
    if cfg.get("ssl_ca"):
        options.update(ssl_ca=cfg["ssl_ca"], ssl_verify_cert=True)
    return mysql.connector.connect(**options)


def run_query(sql, params=(), fetch=False):
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


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + digest.hex()


def check_password(password, stored):
    salt_hex, digest_hex = stored.split(":")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


PUBLIC_USER = ("id, username, login_email, provider, created_at, "
               "password_hash IS NOT NULL AS has_password, totp_secret IS NOT NULL AS has_totp")


def get_user(field, value):
    assert field in ("id", "username", "login_email")
    rows = run_query(f"SELECT {PUBLIC_USER} FROM users WHERE {field} = %s", (value,), fetch=True)
    return rows[0] if rows else None


def create_user(username, email, password):
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
    except mysql.connector.IntegrityError:
        return "That username or email is already taken."


def authenticate(identifier, password):
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
        minutes = -(-row["locked_for"] // 60)
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

    return get_user("id", row["id"]), None


def locked_minutes(user_id):
    rows = run_query("SELECT TIMESTAMPDIFF(SECOND, NOW(), locked_until) AS s FROM users WHERE id = %s",
                     (user_id,), fetch=True)
    seconds = (rows[0]["s"] or 0) if rows else 0
    return -(-seconds // 60) if seconds > 0 else 0


def register_failure(user_id):
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
    rows = run_query("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch=True)
    if not rows or not rows[0]["password_hash"] or not check_password(current, rows[0]["password_hash"]):
        return False
    run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new), user_id))
    return True


def set_first_password(user_id, new):
    return run_query("UPDATE users SET password_hash = %s WHERE id = %s AND password_hash IS NULL",
                     (hash_password(new), user_id)) == 1


def add_login_email(user_id, email):
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
    hashed = ",".join(hashlib.sha256(c.encode()).hexdigest() for c in backup_codes)
    run_query("UPDATE users SET totp_secret = %s, backup_codes = %s WHERE id = %s",
              (secret, hashed, user_id))


def use_backup_code(user_id, code):
    rows = run_query("SELECT backup_codes FROM users WHERE id = %s", (user_id,), fetch=True)
    codes = (rows[0]["backup_codes"] or "").split(",") if rows else []
    digest = hashlib.sha256(code.strip().lower().encode()).hexdigest()
    if digest not in codes:
        return False
    codes.remove(digest)
    run_query("UPDATE users SET backup_codes = %s WHERE id = %s", (",".join(codes), user_id))
    return True


def system_info():
    return run_query("SELECT VERSION() AS version, DATABASE() AS db", fetch=True)[0]


def rows(sql, params=()):
    return run_query(sql, params, fetch=True)


def get_warehouses():
    return rows("SELECT id, name, location FROM warehouses ORDER BY name")


def add_warehouse(name, location):
    try:
        run_query("INSERT INTO warehouses (name, location) VALUES (%s, %s)", (name, location))
    except mysql.connector.IntegrityError:
        return "That warehouse already exists."


def get_products(search=""):
    return rows(
        "SELECT p.id, p.sku, p.name, p.category, p.price, p.cost, p.reorder_level, "
        "COALESCE(SUM(s.qty), 0) AS in_stock FROM products p "
        "LEFT JOIN stock s ON s.product_id = p.id "
        "WHERE p.name LIKE %s OR p.sku LIKE %s OR p.category LIKE %s "
        "GROUP BY p.id ORDER BY p.name", (f"%{search}%",) * 3)


def add_product(sku, name, category, price, cost, reorder_level):
    try:
        run_query("INSERT INTO products (sku, name, category, price, cost, reorder_level) "
                  "VALUES (%s, %s, %s, %s, %s, %s)", (sku, name, category, price, cost, reorder_level))
    except mysql.connector.IntegrityError:
        return "That SKU already exists."


def update_product(product_id, name, category, price, cost, reorder_level):
    run_query("UPDATE products SET name=%s, category=%s, price=%s, cost=%s, reorder_level=%s "
              "WHERE id=%s", (name, category, price, cost, reorder_level, product_id))


def delete_product(product_id):
    try:
        run_query("DELETE FROM stock WHERE product_id = %s", (product_id,))
        run_query("DELETE FROM products WHERE id = %s", (product_id,))
    except mysql.connector.Error:
        return "This product is used in orders, so it can't be deleted."


def get_stock():
    return rows(
        "SELECT p.id AS product_id, p.sku, p.name, p.reorder_level, w.id AS warehouse_id, "
        "w.name AS warehouse, COALESCE(s.qty, 0) AS qty FROM products p "
        "CROSS JOIN warehouses w LEFT JOIN stock s ON s.product_id = p.id AND s.warehouse_id = w.id "
        "ORDER BY p.name, w.name")


def change_stock(product_id, warehouse_id, delta):
    run_query("INSERT INTO stock (product_id, warehouse_id, qty) VALUES (%s, %s, %s) "
              "ON DUPLICATE KEY UPDATE qty = qty + VALUES(qty)", (product_id, warehouse_id, delta))


def transfer_stock(product_id, from_id, to_id, qty):
    have = rows("SELECT qty FROM stock WHERE product_id=%s AND warehouse_id=%s", (product_id, from_id))
    if not have or have[0]["qty"] < qty:
        return "Not enough stock in the source warehouse."
    change_stock(product_id, from_id, -qty)
    change_stock(product_id, to_id, qty)


def get_customers():
    return rows("SELECT id, name, email, phone FROM customers ORDER BY name")


def add_customer(name, email, phone):
    run_query("INSERT INTO customers (name, email, phone) VALUES (%s, %s, %s)", (name, email, phone))


def create_order(customer_id, warehouse_id, items, user_id):
    """items: list of (product_id, qty, unit_price). Returns an error text or None."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        for product_id, qty, _ in items:
            cur.execute("SELECT qty FROM stock WHERE product_id=%s AND warehouse_id=%s FOR UPDATE",
                        (product_id, warehouse_id))
            row = cur.fetchone()
            if not row or row["qty"] < qty:
                conn.rollback()
                return "Not enough stock for one of the products."
        total = sum(qty * price for _, qty, price in items)
        cur.execute("INSERT INTO orders (customer_id, warehouse_id, total, created_by) "
                    "VALUES (%s, %s, %s, %s)", (customer_id, warehouse_id, total, user_id))
        order_id = cur.lastrowid
        for product_id, qty, price in items:
            cur.execute("INSERT INTO order_items (order_id, product_id, qty, unit_price) "
                        "VALUES (%s, %s, %s, %s)", (order_id, product_id, qty, price))
            cur.execute("UPDATE stock SET qty = qty - %s WHERE product_id=%s AND warehouse_id=%s",
                        (qty, product_id, warehouse_id))
        conn.commit()
    except mysql.connector.Error:
        conn.rollback()
        return "An error occurred. The order was not saved."
    finally:
        conn.close()


def get_orders(status=None):
    where, params = ("WHERE o.status = %s", (status,)) if status else ("", ())
    return rows(
        "SELECT o.id, c.name AS customer, w.name AS warehouse, o.status, o.total, "
        "COALESCE((SELECT SUM(amount) FROM payments WHERE order_id = o.id), 0) AS paid, o.created_at "
        f"FROM orders o JOIN customers c ON c.id = o.customer_id JOIN warehouses w ON w.id = o.warehouse_id "
        f"{where} ORDER BY o.created_at DESC", params)


def get_order_items(order_id):
    return rows("SELECT p.name AS product, i.qty, i.unit_price, i.qty * i.unit_price AS line_total "
                "FROM order_items i JOIN products p ON p.id = i.product_id WHERE i.order_id = %s",
                (order_id,))


def set_order_status(order_id, status):
    order = rows("SELECT status, warehouse_id FROM orders WHERE id = %s", (order_id,))[0]
    if status == "cancelled" and order["status"] != "cancelled":
        for item in rows("SELECT product_id, qty FROM order_items WHERE order_id = %s", (order_id,)):
            change_stock(item["product_id"], order["warehouse_id"], item["qty"])
    run_query("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))


def add_payment(order_id, amount, method, note=""):
    order = rows("SELECT o.total, o.status, COALESCE(SUM(p.amount), 0) AS paid FROM orders o "
                 "LEFT JOIN payments p ON p.order_id = o.id WHERE o.id = %s GROUP BY o.id", (order_id,))[0]
    if order["status"] == "cancelled":
        return "This order is cancelled."
    if amount <= 0 or amount > order["total"] - order["paid"]:
        return "The amount must be more than 0 and not more than the balance."
    run_query("INSERT INTO payments (order_id, amount, method, note) VALUES (%s, %s, %s, %s)",
              (order_id, amount, method, note))


def get_payments():
    return rows("SELECT p.id, p.order_id, c.name AS customer, p.amount, p.method, p.note, p.paid_at "
                "FROM payments p JOIN orders o ON o.id = p.order_id JOIN customers c ON c.id = o.customer_id "
                "ORDER BY p.paid_at DESC")


def dashboard(days=30):
    one = lambda sql, *p: rows(sql, p)[0]
    totals = one(
        "SELECT COUNT(*) AS orders, COALESCE(SUM(total), 0) AS sales FROM orders "
        "WHERE status <> 'cancelled' AND created_at >= NOW() - INTERVAL %s DAY", days)
    paid = one("SELECT COALESCE(SUM(p.amount), 0) AS paid FROM payments p JOIN orders o ON o.id = p.order_id "
               "WHERE o.status <> 'cancelled' AND o.created_at >= NOW() - INTERVAL %s DAY", days)["paid"]
    return {
        "orders": totals["orders"], "sales": totals["sales"], "paid": paid,
        "low_stock": one("SELECT COUNT(*) AS n FROM (SELECT p.id FROM products p LEFT JOIN stock s "
                         "ON s.product_id = p.id GROUP BY p.id, p.reorder_level "
                         "HAVING COALESCE(SUM(s.qty), 0) <= p.reorder_level) t")["n"],
        "stock_value": one("SELECT COALESCE(SUM(s.qty * p.cost), 0) AS v FROM stock s "
                           "JOIN products p ON p.id = s.product_id")["v"],
        "per_day": rows("SELECT DATE(created_at) AS day, SUM(total) AS sales FROM orders "
                        "WHERE status <> 'cancelled' AND created_at >= NOW() - INTERVAL %s DAY "
                        "GROUP BY DATE(created_at) ORDER BY day", (days,)),
        "top_products": rows("SELECT p.name, SUM(i.qty) AS sold FROM order_items i "
                             "JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id "
                             "WHERE o.status <> 'cancelled' AND o.created_at >= NOW() - INTERVAL %s DAY "
                             "GROUP BY p.name ORDER BY sold DESC LIMIT 5", (days,)),
        "by_status": rows("SELECT status, COUNT(*) AS orders FROM orders GROUP BY status"),
        "top_customers": rows("SELECT c.name, SUM(o.total) AS spent FROM orders o "
                              "JOIN customers c ON c.id = o.customer_id WHERE o.status <> 'cancelled' "
                              "AND o.created_at >= NOW() - INTERVAL %s DAY GROUP BY c.name "
                              "ORDER BY spent DESC LIMIT 5", (days,)),
    }


WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|replace|drop|alter|truncate|create|rename|grant|revoke|"
    r"load|lock|unlock|call|handler|set|into)\b",
    re.IGNORECASE,
)


def run_select(sql):
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
            conn.start_transaction(readonly=True)
        except mysql.connector.Error:
            conn.start_transaction()
        cur = conn.cursor()
        cur.execute(sql)
        columns, rows = list(cur.column_names), cur.fetchall()
        hidden = [i for i, c in enumerate(columns) if c.lower() in ("password_hash", "login_email", "totp_secret", "backup_codes")]
        for i in reversed(hidden):
            del columns[i]
            rows = [row[:i] + row[i + 1:] for row in rows]
        return columns, rows
    finally:
        conn.rollback()
        conn.close()
