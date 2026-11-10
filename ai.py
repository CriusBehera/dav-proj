import json
import re
from datetime import date

import mysql.connector
import requests
import streamlit as st

import db
import ui

MAX_QUERIES = 3
MAX_ROWS_SENT = 50

SCHEMA = """
products(id, sku, name, category, price, cost, reorder_level, created_at)
warehouses(id, name, location)
stock(product_id -> products.id, warehouse_id -> warehouses.id, qty)   -- units in each warehouse
customers(id, name, email, phone, created_at)
orders(id, customer_id -> customers.id, warehouse_id -> warehouses.id, status, total, created_at)
                                            -- status: pending, shipped, delivered or cancelled
order_items(id, order_id -> orders.id, product_id -> products.id, qty, unit_price)
payments(id, order_id -> orders.id, amount, method, note, paid_at)   -- an order can have several payments
users(id, username, provider, created_at)  -- never select password_hash, login_email, totp_secret or backup_codes
Money is in Indian rupees. Sales exclude cancelled orders. An order's balance = total minus the sum of its payments.""".strip()

PLAN_PROMPT = """You are Nuera Core AI, the assistant inside "Stratex" (a starter project by
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

ANSWER_PROMPT = """You are Nuera Core AI inside "Stratex". Answer the user's question using ONLY
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
    cfg = st.secrets["nuera"]
    try:
        r = requests.post(cfg["url"], json={"email": cfg["email"], "platform": cfg.get("platform", "w"),
                                            "prompt": prompt}, timeout=120)
        data = r.json()
    except (requests.RequestException, ValueError):
        raise AIError("An error occurred. Could not reach Nuera AI.")
    if r.status_code != 200:
        raise AIError("An error occurred. Nuera AI is not available right now.")
    return data.get("text", "")


def parse_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None


def run_queries(queries):
    results = []
    for sql in queries[:MAX_QUERIES]:
        try:
            columns, rows = db.run_select(sql)
            results.append({"sql": sql, "df": ui.to_df(rows, columns), "error": None})
        except (ValueError, mysql.connector.Error) as e:
            results.append({"sql": sql, "df": None, "error": getattr(e, "msg", str(e))})
    return results


def answer(question, messages):
    history = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:500]}"
                        for m in messages[-6:]) or "(none)"
    plan_args = dict(schema=SCHEMA, today=date.today().isoformat(), max_q=MAX_QUERIES,
                     history=history, question=question)
    text = ask_nuera(PLAN_PROMPT.format(extra="", **plan_args))
    plan = parse_json(text)
    if not plan or not plan.get("queries"):
        return {"answer": (plan or {}).get("answer") or text, "results": []}

    results = run_queries(plan["queries"])
    failed = [r for r in results if r["error"]]
    if failed:
        errors = "\n".join(f"- {r['sql']}\n  error: {r['error']}" for r in failed)
        fixed = parse_json(ask_nuera(PLAN_PROMPT.format(
            extra=f"\nYour previous queries failed. Fix them:\n{errors}\n", **plan_args)))
        if fixed and fixed.get("queries"):
            results = [r for r in results if not r["error"]] + run_queries(fixed["queries"])
    if all(r["error"] for r in results):
        return {"answer": "An error occurred. I couldn't read the database to answer that.",
                "results": results}

    parts = [f"Query {n} failed: {r['error']}" if r["error"] else
             f"Query {n} ({len(r['df'])} rows): {r['sql']}\n{r['df'].head(MAX_ROWS_SENT).to_csv(index=False)}"
             for n, r in enumerate(results, 1)]
    text = ask_nuera(ANSWER_PROMPT.format(history=history, question=question, results="\n\n".join(parts)))
    return {"answer": text, "results": results}


SUGGESTIONS = [
    "What were the total sales this month?",
    "Which products are low on stock?",
    "Which orders are still unpaid?",
    "Who are the top 5 customers?",
    "Which product sells the most?",
    "How much stock is in each warehouse?",
]


def show_results(results):
    for n, r in enumerate(results, 1):
        with st.expander(f"Query {n}" + (" (failed)" if r["error"] else f" · {len(r['df'])} rows")):
            st.code(r["sql"], language="sql")
            if r["error"]:
                st.error(r["error"])
                continue
            st.dataframe(r["df"], hide_index=True, alt=f"Result table for query {n}")
            numeric = r["df"].select_dtypes("number").columns
            if len(r["df"].columns) == 2 and len(numeric) == 1 and 1 < len(r["df"]) <= 30:
                st.bar_chart(r["df"], x=r["df"].columns[0], y=numeric[0], height=240,
                             alt=f"Bar chart of {numeric[0]}")


def assistant_page():
    ui.header("Nuera AI", "Ask questions about your sales, stock and customers in plain English.")
    if "nuera" not in st.secrets:
        st.warning("Add a [nuera] section to .streamlit/secrets.toml to turn on the assistant.")
        return
    messages = st.session_state.setdefault("ai_messages", [])
    question = st.chat_input("Ask about your data…")
    if not messages and not question:
        cols = st.columns(2)
        for n, text in enumerate(SUGGESTIONS):
            if cols[n % 2].button(text, width="stretch", key=f"suggest_{n}"):
                question = text

    for m in messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            show_results(m.get("results", []))

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Thinking…"):
                    reply = answer(question, messages)
            except AIError as e:
                st.error(str(e))
                return
            except Exception:
                st.error("An error occurred. Please try again.")
                return
            st.markdown(reply["answer"])
            show_results(reply["results"])
        messages += [{"role": "user", "content": question},
                     {"role": "assistant", "content": reply["answer"], "results": reply["results"]}]
    if messages and st.button("Clear chat", icon=":material/delete_sweep:"):
        messages.clear()
        st.rerun()
