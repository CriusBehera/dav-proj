# Stratex

A small business app on **Streamlit + MySQL**: sales, payments, products and warehouses, with secure sign-in and an AI assistant.

Made by **Crius Behera**, **Reyansh Patel** | DPS Kalinga

## What is already working
- **Sign-in** by username, email or **Google** (Firebase), all in one `users` table.
- **Strong passwords**, lockout after 5 wrong tries, auto sign-out after 30 min.
- **Email verification** through Firebase, then a required **authenticator-app code** (Microsoft Authenticator recommended). Google sign-ins skip both.
- **Nuera Core AI** chatbot that writes read-only SQL on your database and explains the answer.
- **Dashboard**: sales, orders, collected money, outstanding balance, low-stock count, charts, top products and customers.
- **New order**, **Orders** and **Payments**: pick a customer and warehouse, enter quantities (stock is checked and deducted), track status, record part or full payments.
- **Products** and **Warehouse**: catalogue with editable prices, stock per warehouse, receiving stock and transfers between warehouses.
- A plain, default Streamlit look (native sidebar navigation, containers and metrics), easy to restyle with `.streamlit/config.toml`.

## Run it on your computer
1. MySQL 8 running locally, then create the database and tables:
   ```
   mysql -u root < schema.sql
   ```
2. Make a MySQL user for the app (use your own password):
   ```
   mysql -u root -e "CREATE USER 'dav_app'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD'; GRANT ALL ON dav_db.* TO 'dav_app'@'localhost';"
   ```
3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill it in
   (MySQL, Nuera key and the Firebase web settings; see `DEPLOY.md`).
4. `pip install -r requirements.txt` then `streamlit run app.py`.

## Build your own thing
| To add... | Do this |
|---|---|
| A table | Add `CREATE TABLE` to `schema.sql`, run it, and describe it in `SCHEMA` in `ai.py` so the AI knows it |
| Database functions | Add them to `db.py` (always use `%s` parameters) |
| A page | Add a function to `shop.py`, then register it with `st.Page` in `app.py` |
| Look and colours | Add a `.streamlit/config.toml` theme |
| Sign-in rules | `auth.py` |

## Files
| File | What it does |
|---|---|
| `app.py` | Shell: sign-in check, home, sidebar, page registry |
| `auth.py` | Sign in, create account, email check, authenticator code, account page |
| `firebase.py` | Sends and checks the email verification link (Firebase REST API) |
| `db.py` | All MySQL queries, password hashing, lockout, read-only SQL guard |
| `shop.py` | All business pages: dashboard, orders, payments, products, warehouse |
| `ai.py` | Nuera Core AI chatbot |
| `ui.py` | Small shared helpers (cards, stats) |
| `load_db.py` | Loads the tables into a cloud database (TiDB) |
| `schema.sql` | Creates all the tables |

Put it online with **[DEPLOY.md](DEPLOY.md)**.
