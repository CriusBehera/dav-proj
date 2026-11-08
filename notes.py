"""Example app: Notes. Copy this file to start your own page (form + list + delete + SQL)."""
import streamlit as st

import db
import ui

EXAMPLES = [
    {"app": "notes", "title": "All notes, newest first",
     "explain": "`ORDER BY ... DESC` sorts newest first.",
     "sql": "SELECT id, title, created_at FROM notes ORDER BY created_at DESC;"},
    {"app": "notes", "title": "Notes per author (GROUP BY + JOIN)",
     "explain": "`JOIN` links notes to users, `GROUP BY` counts per user.",
     "sql": """SELECT u.username, COUNT(*) AS notes
FROM notes n JOIN users u ON u.id = n.user_id
GROUP BY u.username ORDER BY notes DESC;"""},
]


def overview():
    ui.page_header("Notes", "A tiny example app: add, search and delete notes in MySQL.", "notes", "📝")
    with ui.card("add_note"):
        with st.form("note", clear_on_submit=True, border=False):
            title = st.text_input("Title")
            body = st.text_area("Note")
            if st.form_submit_button("Add note", type="primary"):
                if title.strip():
                    db.add_note(title.strip(), body.strip(), st.session_state.user["id"])
                    ui.flash("Note added", "📝")
                    st.rerun()
                else:
                    st.error("Give the note a title.")
    search = st.text_input("Search", placeholder="Search notes…")
    for note in db.get_notes(search):
        with ui.card(f"note_{note['id']}"):
            st.markdown(f"**{note['title']}**  \n{note['body'] or ''}")
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            c1.caption(f"{note['author'] or 'unknown'} · {note['created_at']:%d %b %Y %H:%M}")
            if c2.button("Delete", key=f"del_{note['id']}", icon=":material/delete:"):
                db.delete_note(note["id"])
                st.rerun()


def sql():
    ui.page_header("SQL playground", "Practise read-only SQL on the notes and users tables.", "notes", "🧮")
    ui.sql_playground(EXAMPLES, "**notes**: id, title, body, user_id, created_at  \n"
                                "**users**: id, username, provider, created_at")


PAGES = [  # (function, title, icon, url path)
    (overview, "Notes", ":material/sticky_note_2:", "notes"),
    (sql, "SQL playground", ":material/code:", "notes-sql"),
]
