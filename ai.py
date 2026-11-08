"""Nuera Core AI assistant: answers questions about the database by writing SQL.

How one question is answered:
  1. Nuera reads the table layout + your question and replies with up to 3
     read-only SQL queries (or a direct answer if no data is needed).
  2. The queries run through db.run_select (same safety checks as the SQL
     playground). If one fails, Nuera gets the error once to fix it.
  3. Nuera reads the results and writes the answer.
"""
import json
import re
import time
import traceback
from datetime import date

import mysql.connector
import pandas as pd
import requests
import streamlit as st

import db
import ui

MAX_QUERIES = 3
MAX_ROWS_SENT = 50  # rows per query sent to the AI (it sees a sample, you see everything)

SCHEMA = """
notes(id, title, body, user_id -> users.id, created_at)
users(id, username, provider, created_at)  -- never select password_hash, login_email, totp_secret or backup_codes
-- Add your own tables here (this text is how the AI learns your database).""".strip()

PLAN_PROMPT = """You are Nuera Core AI, the assistant inside "DAV Project" (a starter project by
Crius Behera and Reyansh Patel). You answer questions about a MySQL 8 database by writing SQL.

Tables:
{schema}

Today is {today}.

Reply with ONLY a JSON object, no code fences, in one of these two shapes:
  {{"queries": ["SELECT ...", "SELECT ..."]}}   -> when the question needs data (1 to {max_q} queries)
  {{"answer": "..."}}                          -> greetings, SQL explanations, or questions about you

Rules for queries:
- MySQL syntax, read-only: SELECT or WITH only, one statement each, no semicolons.
- Never use INSERT, UPDATE, DELETE, SET, INTO, or the password_hash / login_email columns.
- Add ORDER BY and LIMIT 50 (or less) to queries that return many rows.
- Round averages with ROUND(x, 1). Join tables to show names, not ids.
- For "analyse" or "summary" questions, use up to {max_q} queries that cover different angles.
{extra}
Conversation so far:
{history}

User: {question}"""

ANSWER_PROMPT = """You are Nuera Core AI inside "DAV Project". Answer the user's question using ONLY
the query results below. Write in friendly, clear Markdown:
- Start with the direct answer in one or two sentences (bold the key numbers or names).
- Then add 2 to 4 short bullet-point insights if they are useful.
- If a result is empty, say no matching data was found.
- Don't show the SQL or talk about JSON. Keep it under 200 words unless asked for detail.

Conversation so far:
{history}

User: {question}

Query results:
{results}"""


class AIError(Exception):
    pass


def ask_nuera(prompt):
    """Send one prompt to Nuera Core AI. Returns (text, tokens used)."""
    cfg = st.secrets["nuera"]
    try:
        r = requests.post(
            cfg["url"],
            json={"email": cfg["email"], "platform": cfg.get("platform", "w"), "prompt": prompt},
            timeout=120,
        )
        data = r.json()
    except requests.RequestException:
        raise AIError("Couldn't reach Nuera Core AI. Check your internet connection.")
    except ValueError:
        raise AIError(f"Nuera Core AI sent an unexpected reply (HTTP {r.status_code}).")
    if r.status_code != 200:
        raise AIError(f"Nuera Core AI: {data.get('error', f'HTTP {r.status_code}')}")
    return data.get("text", ""), data.get("usage", {}).get("total_token_count", 0)


def parse_json(text):
    """Pull the first {...} object out of the AI's reply."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def history_text(messages, limit=6):
    lines = []
    for m in messages[-limit:]:
        who = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{who}: {m['content'][:500]}")
    return "\n".join(lines) or "(none)"


def run_queries(queries):
    results = []
    for sql in queries[:MAX_QUERIES]:
        try:
            columns, rows = db.run_select(sql)
            results.append({"sql": sql, "df": ui.to_df(rows, columns), "error": None})
        except (ValueError, mysql.connector.Error) as e:
            results.append({"sql": sql, "df": None, "error": getattr(e, "msg", str(e))})
    return results


class Trace:
    """Step-by-step log of one answer, shown when Debug mode is on."""

    def __init__(self):
        self.start = time.time()
        self.steps = []

    def add(self, step, detail="", data=None):
        self.steps.append({"t": time.time() - self.start, "step": step,
                           "detail": detail, "data": data})


def answer(question, messages):
    """Answer one question. Returns {"answer", "results", "tokens", "trace", "db_error"}."""
    trace = Trace()
    history = history_text(messages)
    plan_args = dict(schema=SCHEMA, today=date.today().isoformat(), max_q=MAX_QUERIES,
                     history=history, question=question)
    reply = {"results": [], "tokens": 0, "trace": trace.steps, "db_error": None}

    prompt = PLAN_PROMPT.format(extra="", **plan_args)
    trace.add("1. Ask Nuera for a plan", f"prompt: {len(prompt):,} characters")
    text, tokens = ask_nuera(prompt)
    plan = parse_json(text)
    trace.add("Nuera replied", f"{tokens:,} tokens · parsed as JSON: {plan is not None}",
              {"raw reply": text, "parsed plan": plan})
    reply["tokens"] = tokens
    if not plan or not plan.get("queries"):
        trace.add("No queries needed", "answering directly")
        return reply | {"answer": (plan or {}).get("answer") or text}

    results = run_queries(plan["queries"])
    for r in results:
        trace.add("2. Run SQL", r["error"] and f"❌ {r['error']}" or f"✅ {len(r['df'])} rows",
                  {"sql": r["sql"]})
    failed = [r for r in results if r["error"]]
    if failed:  # give the AI one chance to fix its SQL
        errors = "\n".join(f"- {r['sql']}\n  error: {r['error']}" for r in failed)
        extra = f"\nYour previous queries failed. Fix them:\n{errors}\n"
        trace.add("3. Ask Nuera to fix the failed queries", f"{len(failed)} failed")
        text, more = ask_nuera(PLAN_PROMPT.format(extra=extra, **plan_args))
        reply["tokens"] += more
        fixed = parse_json(text)
        trace.add("Nuera replied", f"{more:,} tokens", {"raw reply": text, "parsed plan": fixed})
        if fixed and fixed.get("queries"):
            retried = run_queries(fixed["queries"])
            for r in retried:
                trace.add("Run fixed SQL", r["error"] and f"❌ {r['error']}" or
                          f"✅ {len(r['df'])} rows", {"sql": r["sql"]})
            results = [r for r in results if not r["error"]] + retried
    reply["results"] = results

    if all(r["error"] for r in results):  # nothing worked: show the real database error
        reply["db_error"] = results[-1]["error"]
        trace.add("Stopped", "every query failed")
        return reply | {"answer": "I couldn't read the database to answer that."}

    parts = []
    for n, r in enumerate(results, 1):
        if r["error"]:
            parts.append(f"Query {n} failed: {r['error']}")
        else:
            csv = r["df"].head(MAX_ROWS_SENT).to_csv(index=False)
            parts.append(f"Query {n} ({len(r['df'])} rows): {r['sql']}\n{csv}")
    prompt = ANSWER_PROMPT.format(history=history, question=question, results="\n\n".join(parts))
    trace.add("4. Ask Nuera to explain the results", f"prompt: {len(prompt):,} characters")
    text, more = ask_nuera(prompt)
    reply["tokens"] += more
    trace.add("Done", f"{more:,} tokens · {reply['tokens']:,} total")
    return reply | {"answer": text}


# ---------- Chat page ----------

SUGGESTIONS = [
    "📝 How many notes are there?",
    "🕒 Show the newest notes",
    "👥 Who wrote the most notes?",
    "📊 Summarise the database",
]


def show_results(results):
    for n, r in enumerate(results, 1):
        label = f"🔍 Query {n}" + (" (failed)" if r["error"] else f" · {len(r['df'])} rows")
        with st.expander(label):
            st.code(r["sql"], language="sql")
            if r["error"]:
                st.error(r["error"])
                continue
            df = r["df"]
            st.dataframe(df, hide_index=True, width="stretch")
            numeric = df.select_dtypes("number").columns
            if len(df.columns) == 2 and len(numeric) == 1 and 1 < len(df) <= 30:
                st.bar_chart(df, x=df.columns[0], y=numeric[0], height=240)


def show_debug(trace):
    with st.expander("🐞 Debug: step by step", expanded=False):
        for s in trace:
            st.markdown(f"`{s['t']:5.1f}s` **{s['step']}** {s['detail']}")
            if s["data"]:
                st.json(s["data"], expanded=False)


def show_reply(m, debug):
    st.markdown(m["content"])
    if m.get("db_error"):
        st.error(f"**Database error:** {m['db_error']}", icon=":material/database:")
    show_results(m.get("results", []))
    if debug and m.get("trace"):
        show_debug(m["trace"])


def system_check():
    """Quick tests for the Debug panel: secrets, Nuera Core AI and the database."""
    nuera = st.secrets.get("nuera", {})
    mysql_cfg = st.secrets.get("mysql", {})
    st.markdown(f"**Secrets** · `[nuera]` keys: `{sorted(nuera)}` · `[mysql]` keys: `{sorted(mysql_cfg)}`")
    try:
        t = time.time()
        r = requests.post(nuera["url"], json={"email": nuera["email"], "platform":
                          nuera.get("platform", "w"), "prompt": "%SUB-STATE%"}, timeout=60)
        st.markdown(f"**Nuera Core AI** · HTTP {r.status_code} in {time.time() - t:.1f}s")
        st.json(r.json(), expanded=False)
    except Exception as e:  # show anything, this is a debug tool
        st.error(f"Nuera Core AI: {type(e).__name__}: {e}")
    for sql in ["SELECT COUNT(*) AS notes FROM notes",
                "SELECT title FROM notes ORDER BY created_at DESC LIMIT 1"]:
        try:
            t = time.time()
            columns, rows = db.run_select(sql)
            st.markdown(f"**Database** · ✅ `{sql}` → {dict(zip(columns, rows[0])) if rows else 'no rows'} "
                        f"({time.time() - t:.1f}s)")
        except Exception as e:
            st.error(f"Database · `{sql}` → {type(e).__name__}: {getattr(e, 'msg', e)}")


def assistant_page():
    ui.hero("Nuera Core AI", "Ask questions about your data. "
            "It writes the SQL, runs it on your database and explains the answer.",
            "ai", tag="AI assistant")
    if "nuera" not in st.secrets:
        st.warning("Add a `[nuera]` section to `.streamlit/secrets.toml` to turn on the assistant.")
        return

    debug = st.toggle("🐞 Debug mode", key="ai_debug",
                      help="Show each step: Nuera's raw replies, the SQL, errors and timings.")
    if debug:
        with st.expander("🩺 System check", expanded=True):
            if st.button("Run checks", icon=":material/play_arrow:"):
                system_check()

    messages = st.session_state.setdefault("ai_messages", [])
    question = st.chat_input("Ask about your data…")

    if not messages and not question:
        st.markdown("**Try asking:**")
        cols = st.columns(2)
        for n, text in enumerate(SUGGESTIONS):
            if cols[n % 2].button(text, width="stretch", key=f"suggest_{n}"):
                question = text.split(" ", 1)[1]

    for m in messages:
        with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "✨"):
            show_reply(m, debug) if m["role"] == "assistant" else st.markdown(m["content"])

    if question:
        with st.chat_message("user", avatar="🧑"):
            st.markdown(question)
        with st.chat_message("assistant", avatar="✨"):
            try:
                with st.status("Nuera is thinking…", expanded=False) as status:
                    status.update(label="Writing SQL and reading your database…")
                    reply = answer(question, messages)
                    status.update(label=f"Done · {reply['tokens']:,} tokens", state="complete")
            except AIError as e:
                st.error(str(e))
                return
            except Exception as e:  # anything unexpected: say what, and show details in Debug mode
                st.error(f"Something went wrong: {type(e).__name__}: {e}")
                if debug:
                    st.code(traceback.format_exc())
                return
            message = {"role": "assistant", "content": reply["answer"], "results": reply["results"],
                       "trace": reply["trace"], "db_error": reply["db_error"]}
            show_reply(message, debug)
        messages += [{"role": "user", "content": question}, message]

    if messages:
        c1, c2 = st.columns([4, 1])
        c1.caption("Nuera only reads data: every query runs read-only, and password hashes are hidden.")
        if c2.button("Clear chat", icon=":material/delete_sweep:", width="stretch"):
            messages.clear()
            st.rerun()
    st.markdown("<div class='credits'>Powered by <b>Nuera Core AI</b> · ai.criusbehera.com</div>",
                unsafe_allow_html=True)
