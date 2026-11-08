# dav-proj

A ready-to-edit starter: **Streamlit + MySQL** with sign-in, an AI chatbot and one example app.
Copy it, rename things, and build your own pages on top.

Made by **Crius Behera** · Sponsored by **Nuera Core AI**, **Crius Software Solutions**

## What is already working
- **Sign-in** by username, email or **Google** (Firebase), all in one `users` table.
- **Strong passwords**, lockout after 5 wrong tries, auto sign-out after 30 min.
- **Email verification** through Firebase, then a required **authenticator-app code** (Microsoft Authenticator recommended). Google sign-ins skip both.
- **Nuera Core AI** chatbot that writes read-only SQL on your database and explains the answer.
- **Notes**: a tiny example app (form, list, delete, SQL playground) to copy.
- A modern UI (dark sidebar, glass cards, purple glow that follows the cursor).

## Run it on your computer
1. MySQL 8 running locally, then create the database and sample rows:
   ```
   mysql -u root < schema.sql
   mysql -u root dav_db < sample_data.sql
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
| A page | Copy `notes.py`, edit its `PAGES` list, then register the module in `build_pages()` and `sidebar()` in `app.py` |
| Look and colours | `ui.py` (CSS and `GRADIENTS`) and `.streamlit/config.toml` |
| Sign-in rules | `auth.py` |

## Files
| File | What it does |
|---|---|
| `app.py` | Shell: sign-in check, home, sidebar, page registry |
| `auth.py` | Sign in, create account, email check, authenticator code, account page |
| `firebase.py` | Sends and checks the email verification link (Firebase REST API) |
| `db.py` | All MySQL queries, password hashing, lockout, read-only SQL guard |
| `notes.py` | Example app to copy |
| `ai.py` | Nuera Core AI chatbot |
| `ui.py` | Shared styles and helpers |
| `load_db.py` | Loads the tables into a cloud database (TiDB) |
| `schema.sql`, `sample_data.sql` | Tables and example rows |
| `migrate_auth.sql`, `migrate_totp.sql` | Only for older databases that predate those columns |

Put it online with **[DEPLOY.md](DEPLOY.md)**.
