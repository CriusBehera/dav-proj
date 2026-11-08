# New-project checklist (do these once, in this order)

1. **GitHub**: GitHub Desktop → File → Add Local Repository → this folder → Publish repository as `dav-proj`.
2. **TiDB (online MySQL)**: create a Starter cluster, load tables with `load_db.py` (Step 2 below).
3. **Firebase**: new project → Authentication → turn on **Email/Password** and **Google** → copy the web config.
4. **Streamlit Cloud**: create the app from the repo, paste the secrets (`[mysql]`, `[nuera]`, `[firebase]`).
5. Firebase → Authentication → Settings → **Authorized domains** → add `YOUR-APP.streamlit.app` (Google sign-in needs it).
6. Open the live link, create an account, check the email, set up the authenticator.

Secrets live in `.streamlit/secrets.toml` locally (gitignored) and in Streamlit Cloud → Settings → Secrets online.
`[firebase]` holds `api_key`, `auth_domain` and `project_id` from the Firebase web config.
Google sign-in uses Firebase's pop-up, so no Google Cloud OAuth client is needed.

---

# Putting dav-proj online (Streamlit Community Cloud)

Streamlit Community Cloud runs your app for free at a link like
`https://your-name-db-os.streamlit.app`. One catch: the MySQL on your Mac is
**not reachable from the internet**, so the online app needs a MySQL-compatible
database in the cloud too.

```
GitHub repo ──► Streamlit Cloud (runs app.py) ──► TiDB Cloud (MySQL-compatible)
```

---

## Step 1: Create a free TiDB Cloud database (sign in with Google)

[TiDB Cloud Starter](https://www.pingcap.com/tidb-cloud-pricing/) is free, needs
no credit card, and speaks MySQL.

1. Go to [tidbcloud.com](https://tidbcloud.com) → **Sign up** → **Continue with Google**.
2. Create a **Starter** cluster (a default one may already be made for you).
   Pick a region near you, e.g. Mumbai or Singapore.
3. Open the cluster → click **Connect** (top right).
4. Click **Generate Password** and **copy it somewhere safe**. It's shown only once.
5. Note the **Host** (like `gateway01.ap-south-1.prod.aws.tidbcloud.com`),
   **Port** (`4000`) and **User** (like `3xAbCdEf.root`).

No certificate file is needed: TiDB uses a normal public certificate that every
computer already has.

## Step 2: Load the tables and sample data

In Terminal, from this project folder (put in your host and user):

```bash
python3 load_db.py --host YOUR_HOST --user YOUR_USER
```

It asks for the password, loads `schema.sql` and `sample_data.sql`, and prints
the row counts (a couple of sample notes).
(Newer Homebrew `mysql` command line tools can't log in to TiDB, which is why
this uses Python.)

## Step 3: Put the code on GitHub

Use GitHub Desktop: **File → Add Local Repository** → this folder →
**Publish repository**. Later changes: write a summary → **Commit to main** →
**Push origin**.

`.gitignore` keeps `.streamlit/secrets.toml` (your passwords) **off** GitHub.

## Step 4: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Repository: `YOUR-GITHUB-NAME/dav-proj` · Branch: `main` · Main file: `app.py`.
4. Open **Advanced settings** → **Secrets** and paste (with your TiDB values):

   ```toml
   [mysql]
   host = "gateway01.ap-south-1.prod.aws.tidbcloud.com"
   port = 4000
   user = "3xAbCdEf.root"
   password = "your-tidb-password"
   database = "dav_db"
   ssl_ca = "/etc/ssl/certs/ca-certificates.crt"

   [nuera]
   email = "your-nuera-access-key"
   platform = "w"
   url = "https://nueracoreai-pro-get-ai.criusbehera.com"
   ```

   The `[nuera]` part turns on the Nuera Core AI chatbot. Copy the key from your
   local `.streamlit/secrets.toml`.

5. Click **Deploy**. The first start takes a minute or two while it installs
   `requirements.txt`.

## Updating later

Push new commits to `main` and Streamlit Cloud redeploys on its own.
To change the database login, open your app's menu (⋮) → **Settings → Secrets**.

## If something goes wrong

| What you see | What to check |
|---|---|
| `Database error: Can't connect` | Host, port and user in Secrets (TiDB users look like `xxxx.root`) |
| `SSL` / certificate error | `ssl_ca = "/etc/ssl/certs/ca-certificates.crt"` is in Secrets |
| `Access denied` | Password: generate a new one in TiDB → Connect, and update Secrets |
| `Table ... doesn't exist` | You skipped Step 2 |
| `ModuleNotFoundError` | The package is missing from `requirements.txt` |
| Changes not showing | App menu (⋮) → **Reboot app** |

> **Other hosts.** Any MySQL host works the same way. For a host with its own
> certificate (for example Aiven), download its `ca.pem` into this folder,
> commit it, and set `ssl_ca = "ca.pem"`.

---

# Email verification (Firebase Authentication)

Username/email + password accounts must **verify their email**: signing up (or signing in for the
first time) makes Firebase email a link, and sign-in is blocked until it's clicked. Firebase only
sends the link and tracks "verified"; your users, passwords and lockout stay in MySQL.
Google sign-ins skip it (Google already verified the address) and are untouched.

## Set up (free, about 5 minutes)

1. Go to [console.firebase.google.com](https://console.firebase.google.com) → **Add project** (name it `db-os`; Analytics off is fine).
   You can pick your existing Google Cloud project `db-os-513907`.
2. **Build → Authentication → Get started → Sign-in method → Email/Password → Enable** (leave "Email link" off) → Save.
3. **Project settings (gear) → General → Web API Key**: copy it.
4. Add it to `.streamlit/secrets.toml` and to Streamlit Cloud → Settings → Secrets:

```toml
[firebase]
api_key = "AIza..."
```

5. Optional: **Authentication → Templates → Email address verification** lets you rename the sender and edit the text.

Older accounts without an email are asked to add one at their next sign-in. Existing
accounts are copied to Firebase automatically the first time they sign in.

---

# Two-step sign-in (authenticator app, required)

After the password and the verified email, every password sign-in needs a 6-digit code from an
authenticator app. We recommend **Microsoft Authenticator** (Google Authenticator and Authy work too).
The first time, a QR code and 8 one-time backup codes are shown and the user must confirm a code
before getting in. Google sign-ins skip it. Add the columns once:

```bash
mysql -u root dav_db < migrate_totp.sql                                   # local (already done)
python3 load_db.py --host YOUR_HOST --user YOUR_USER --file migrate_totp.sql # TiDB (online)
```
