"""Shared look and helpers used by every app in DAV Project."""
import itertools
from datetime import datetime
from decimal import Decimal
from html import escape

import mysql.connector
import pandas as pd
import streamlit as st

import db

CREDITS = "By <b>Crius Behera</b>, <b>Reyansh Patel</b> · Delhi Public School Kalinga"

# Gradient for each app's banner and icon chips
GRADIENTS = {
    "os": "linear-gradient(135deg, #0B1020 0%, #312E81 55%, #4F46E5 100%)",
    "notes": "linear-gradient(135deg, #4F46E5 0%, #8B5CF6 55%, #EC4899 100%)",
    "ai": "linear-gradient(135deg, #7C3AED 0%, #C026D3 50%, #F97316 100%)",
}
APP_NAMES = {"os": None, "notes": "Notes", "ai": "Nuera AI"}

CSS = """
<style>
:root {
  --ink: #0F172A; --muted: #64748B; --line: rgba(203,210,224,.65); --card: rgba(255,255,255,.78);
  --brand: #4F46E5; --glass: blur(16px) saturate(150%);
  --shadow: 0 1px 2px rgba(16,24,40,.04), 0 6px 18px -8px rgba(16,24,40,.10);
  --shadow-lg: 0 18px 40px -20px rgba(15,23,42,.35);
}

/* ----- Moving background + cursor glow (made by FX_SCRIPT) ----- */
body { background: #F4F6FB; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: transparent !important; }
.stApp { z-index: 1; }  /* keep Streamlit's own position: it makes the app fill the window */
#fx-layer { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.fx-blob { position: absolute; border-radius: 50%; filter: blur(90px);
  animation: fx-drift 24s ease-in-out infinite alternate; }
.fx-blob.b1 { width: 560px; height: 560px; background: #C4B5FD; opacity: .50; top: -160px; right: -60px; }
.fx-blob.b2 { width: 480px; height: 480px; background: #99F6E4; opacity: .40; bottom: -180px; left: 18%;
  animation-duration: 30s; }
.fx-blob.b3 { width: 400px; height: 400px; background: #F9A8D4; opacity: .30; top: 38%; right: 22%;
  animation-duration: 36s; animation-direction: alternate-reverse; }
#fx-glow { position: absolute; left: 0; top: 0; width: 620px; height: 620px; border-radius: 50%;
  background: radial-gradient(circle, rgba(139,92,246,.58) 0%, rgba(124,58,237,.26) 36%, transparent 70%);
  filter: blur(30px); opacity: 0; transition: opacity .5s ease; will-change: transform; }
@keyframes fx-drift {
  0%   { transform: translate(0, 0) scale(1); }
  50%  { transform: translate(-70px, 50px) scale(1.08); }
  100% { transform: translate(50px, -40px) scale(.94); }
}
@media (prefers-reduced-motion: reduce) { .fx-blob { animation: none; } #fx-glow { display: none; } }
div[data-testid="stElementContainer"]:has(#fx-boot) { display: none; }

/* ----- Streamlit chrome ----- */
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 1.3rem; padding-bottom: 3rem; max-width: 1240px; }
h1, h2, h3 { letter-spacing: -.02em; }
/* no "link to heading" icons on our HTML headings */
.hero [data-testid="stHeaderActionElements"], .ph [data-testid="stHeaderActionElements"],
.tile [data-testid="stHeaderActionElements"], .auth-panel [data-testid="stHeaderActionElements"],
.auth-head [data-testid="stHeaderActionElements"], .hero h1 a, .ph h1 a, .tile h3 a,
.auth-panel h1 a, .auth-head h2 a { display: none !important; }

/* ----- Cards: ui.card() gives a container the key card_* ----- */
div[class*="st-key-card_"] {
  background: var(--card); backdrop-filter: var(--glass); -webkit-backdrop-filter: var(--glass); border: 1px solid var(--line); border-radius: 16px;
  padding: 1.1rem 1.25rem 1.2rem; box-shadow: var(--shadow);
}
div[class*="st-key-card_"] h3 { font-size: 1rem; font-weight: 700; padding: 0 0 .2rem; }
div[class*="st-key-card_tile"] { transition: transform .15s ease, box-shadow .15s ease; }
div[class*="st-key-card_tile"]:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }

/* ----- Metrics look like small cards (but not inside a card) ----- */
[data-testid="stMetric"] {
  background: var(--card); backdrop-filter: var(--glass); -webkit-backdrop-filter: var(--glass); border: 1px solid var(--line); border-radius: 14px;
  padding: .85rem 1rem; box-shadow: var(--shadow);
}
div[class*="st-key-card_"] [data-testid="stMetric"] { background: none; border: 0; box-shadow: none; padding: 0; }
[data-testid="stMetricLabel"] p { font-size: .8rem; font-weight: 600; color: var(--muted); }
[data-testid="stMetricValue"] { font-weight: 750; letter-spacing: -.02em; }

/* ----- Buttons ----- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: linear-gradient(135deg, #4F46E5, #7C3AED); border: 0; font-weight: 600;
  box-shadow: 0 6px 16px -6px rgba(79,70,229,.6); transition: transform .12s, box-shadow .12s;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  transform: translateY(-1px); box-shadow: 0 10px 22px -8px rgba(79,70,229,.7);
}
[data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-primaryFormSubmit"]:disabled {
  background: #E8EBF2; color: #98A2B3; box-shadow: none; transform: none; }
[data-testid="stBaseButton-secondary"] { font-weight: 550; }
.profile { display: flex; align-items: center; gap: .9rem; margin: .3rem 0 1rem; }
.profile .avatar { width: 56px; height: 56px; font-size: 1.4rem; }
.profile b { font-size: 1.1rem; } .profile small { display: block; color: var(--muted); }

/* ----- Top bar + page header ----- */
.topbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  font-size: .84rem; color: var(--muted); margin-bottom: 1.1rem; flex-wrap: wrap; }
.crumbs b { color: var(--ink); font-weight: 600; }
.crumbs .sep { margin: 0 .45rem; opacity: .45; }
.chips { display: flex; gap: .5rem; }
.chip { display: inline-flex; align-items: center; gap: .45rem; background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: .28rem .75rem; font-size: .78rem;
  color: #334155; font-weight: 500; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #22C55E;
  box-shadow: 0 0 0 3px rgba(34,197,94,.18); }
.ph { display: flex; gap: 1rem; align-items: center; margin: 0 0 1.4rem; }
.ph-icon, .tile-icon { display: flex; align-items: center; justify-content: center; color: #fff;
  flex-shrink: 0; box-shadow: 0 8px 18px -8px rgba(15,23,42,.5); }
.ph-icon { width: 50px; height: 50px; border-radius: 14px; font-size: 1.45rem; }
.ph h1 { font-size: 1.7rem; margin: 0; padding: 0; line-height: 1.15; }
.ph p { margin: .2rem 0 0; color: var(--muted); font-size: .95rem; }

/* ----- Hero banner (app overviews) ----- */
.hero { position: relative; overflow: hidden; padding: 1.8rem 2rem; border-radius: 20px;
  color: #fff; margin-bottom: 1.3rem; box-shadow: var(--shadow-lg); }
.hero::before, .hero::after { content: ""; position: absolute; border-radius: 50%; }
.hero::before { width: 300px; height: 300px; right: -70px; top: -120px; background: rgba(255,255,255,.10); }
.hero::after { width: 180px; height: 180px; right: 170px; bottom: -110px; background: rgba(255,255,255,.07); }
.hero h1 { color: #fff; margin: 0; padding: 0; font-size: 2rem; position: relative; }
.hero p { margin: .4rem 0 0; opacity: .88; font-size: 1.02rem; max-width: 640px; position: relative; }
.hero .tag { display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; padding: .25rem .65rem; border-radius: 999px;
  background: rgba(255,255,255,.18); margin-bottom: .7rem; position: relative; }

/* ----- Stat tiles (ui.stats) ----- */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(105px, 1fr)); gap: .65rem; }
.stat { background: #F8FAFC; border: 1px solid #EEF1F6; border-radius: 12px; padding: .75rem .9rem; }
.stat span { display: block; font-size: .74rem; color: var(--muted); font-weight: 600; }
.stat b { font-size: 1.15rem; color: var(--ink); letter-spacing: -.01em; }

/* ----- Home launcher tiles ----- */
.tile-icon { width: 54px; height: 54px; border-radius: 16px; font-size: 1.7rem; margin-bottom: .8rem; }
.tile h3 { margin: 0; padding: 0; font-size: 1.2rem; }
.tile p { color: var(--muted); margin: .3rem 0 1rem; font-size: .93rem; min-height: 2.6em; }
.section { font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--muted); margin: .4rem 0 .6rem; }

/* ----- Sidebar ----- */
[data-testid="stSidebarUserContent"] { padding-top: .2rem; }
.sb-brand { display: flex; align-items: center; gap: .7rem; padding: 0 .3rem 1rem; }
.sb-logo { width: 38px; height: 38px; border-radius: 11px; color: #fff; font-weight: 800;
  font-size: .9rem; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #4F46E5, #14B8A6); box-shadow: 0 6px 16px -6px rgba(79,70,229,.8); }
.sb-brand b { color: #fff; font-size: 1.05rem; }
.sb-brand small { display: block; color: #6B7590; font-size: .72rem; }
.sb-label { font-size: .66rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: #586380; margin: 1.1rem .55rem .35rem; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] { border-radius: 10px; padding: .42rem .65rem; background: none; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover { background: #151C30; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p { color: #B8C0D0; font-weight: 500; font-size: .92rem; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] { color: #7C86A2; }
div[class*="st-key-nav_active"] [data-testid="stPageLink-NavLink"] {
  background: linear-gradient(90deg, rgba(99,102,241,.30), rgba(99,102,241,.06));
  box-shadow: inset 3px 0 0 #818CF8; }
div[class*="st-key-nav_active"] [data-testid="stPageLink-NavLink"] p { color: #fff; font-weight: 600; }
div[class*="st-key-nav_active"] [data-testid="stIconMaterial"] { color: #A5B4FC !important; }
div.st-key-sb_user { background: #121931; border: 1px solid #1E2638; border-radius: 14px; padding: .8rem; margin-top: .8rem; }
.sb-user { display: flex; align-items: center; gap: .65rem; }
.avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-weight: 700; color: #fff; flex-shrink: 0;
  background: linear-gradient(135deg, #EC4899, #8B5CF6); }
.sb-user b { color: #fff; font-size: .92rem; }
.sb-user small { color: #6B7590; display: block; font-size: .74rem; }
.sb-credits { font-size: .7rem; color: #586380; text-align: center; margin-top: 1rem; line-height: 1.55; }
.sb-credits b { color: #8B93A7; font-weight: 600; }

/* ----- Sign-in split screen ----- */
.auth-panel { min-height: 82vh; border-radius: 24px; padding: 2.4rem 2.6rem; color: #fff;
  position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between;
  background: radial-gradient(circle at 85% 0%, rgba(20,184,166,.35), transparent 45%),
              radial-gradient(circle at 0% 100%, rgba(236,72,153,.30), transparent 45%),
              linear-gradient(150deg, #0B1020 0%, #1E1B4B 55%, #4F46E5 100%);
  box-shadow: var(--shadow-lg); }
.auth-panel .sb-logo { width: 46px; height: 46px; font-size: 1.05rem; border-radius: 13px; }
.auth-panel h1 { color: #fff; font-size: 2.6rem; line-height: 1.1; margin: 1.6rem 0 .6rem; padding: 0; }
.auth-panel h1 span { background: linear-gradient(90deg, #A5B4FC, #5EEAD4); -webkit-background-clip: text;
  background-clip: text; color: transparent; }
.auth-panel .lead { color: #C7D2FE; font-size: 1.05rem; max-width: 430px; }
.feature { display: flex; gap: .85rem; align-items: flex-start; margin-top: 1rem;
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.10); border-radius: 14px; padding: .8rem .9rem; }
.feature .fi { font-size: 1.3rem; width: 38px; height: 38px; border-radius: 10px; display: flex;
  align-items: center; justify-content: center; background: rgba(255,255,255,.10); flex-shrink: 0; }
.feature b { color: #fff; } .feature small { color: #A5B4FC; display: block; font-size: .84rem; }
.auth-foot { font-size: .78rem; color: #8B93C7; margin-top: 1.6rem; }
.auth-foot b { color: #C7D2FE; font-weight: 600; }
.auth-head { margin: 9vh 0 1.2rem; }
.auth-head h2 { font-size: 1.75rem; margin: 0; padding: 0; }
.auth-head p { color: var(--muted); margin: .3rem 0 0; }
.or { display: flex; align-items: center; gap: .8rem; color: var(--muted); font-size: .8rem; margin: .5rem 0 .2rem; }
.or::before, .or::after { content: ""; flex: 1; height: 1px; background: var(--line); }

@media (max-width: 768px) {   /* phones: short brand banner, form straight after it */
  .auth-panel { min-height: auto; padding: 1.4rem 1.5rem; }
  .auth-panel h1 { font-size: 1.7rem; margin: 1rem 0 .3rem; }
  .auth-panel .feature, .auth-foot { display: none; }
  .auth-head { margin: 1.2rem 0 .8rem; }
  .hero { padding: 1.3rem 1.4rem; } .hero h1 { font-size: 1.5rem; }
}

/* ----- Chat, expanders, tables ----- */
[data-testid="stChatMessage"] { background: var(--card); backdrop-filter: var(--glass); -webkit-backdrop-filter: var(--glass); border: 1px solid var(--line);
  border-radius: 16px; padding: .9rem 1.1rem; box-shadow: var(--shadow); }
[data-testid="stExpander"] details { background: var(--card); border-radius: 12px; }
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
[data-baseweb="tab-list"] { gap: .3rem; }

.muted { color: var(--muted); font-size: .92rem; }
.credits { text-align: center; color: var(--muted); font-size: .8rem; margin: 2.2rem 0 .5rem; }
.credits b { color: #334155; font-weight: 600; }
</style>
"""

# Adds the drifting colour blobs and a purple glow that follows the mouse.
# Runs once per browser tab (it checks for #fx-layer first).
FX_SCRIPT = """
<span id="fx-boot"></span>
<script>
(() => {
  if (document.getElementById("fx-layer")) return;
  const make = (id, cls) => {
    const el = document.createElement("div");
    if (id) el.id = id;
    if (cls) el.className = cls;
    return el;
  };
  const layer = make("fx-layer");
  for (const b of ["b1", "b2", "b3"]) layer.append(make(null, "fx-blob " + b));
  const glow = make("fx-glow");
  layer.append(glow);
  document.body.prepend(layer);

  let x = innerWidth / 2, y = innerHeight / 3, tx = x, ty = y;
  addEventListener("pointermove", e => {
    if (e.pointerType !== "mouse") return;           // touch screens: background only
    tx = e.clientX; ty = e.clientY; glow.style.opacity = 1;
  }, { passive: true });
  document.documentElement.addEventListener("mouseleave", () => glow.style.opacity = 0);
  (function follow() {                               // ease towards the cursor for a soft trail
    x += (tx - x) * 0.12; y += (ty - y) * 0.12;
    glow.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    requestAnimationFrame(follow);
  })();
})();
</script>
"""

_card_ids = itertools.count()


def apply_style():
    global _card_ids
    _card_ids = itertools.count()  # card keys restart every run, so they stay stable
    st.markdown(CSS, unsafe_allow_html=True)
    st.html(FX_SCRIPT, unsafe_allow_javascript=True)


def card(name=None):
    """A white card (a container styled by the st-key-card_* CSS rule)."""
    return st.container(key=f"card_{name or next(_card_ids)}")


def topbar(app="os", page=None):
    crumbs = [c for c in ("DAV Project", APP_NAMES.get(app), page) if c]
    trail = "<span class='sep'>/</span>".join(
        f"<b>{escape(c)}</b>" if n == len(crumbs) - 1 else escape(c) for n, c in enumerate(crumbs))
    st.markdown(
        f"<div class='topbar'><div class='crumbs'>{trail}</div><div class='chips'>"
        f"<span class='chip'><span class='dot'></span>MySQL connected</span>"
        f"<span class='chip'>📅 {datetime.now():%a, %d %b}</span></div></div>",
        unsafe_allow_html=True,
    )


def hero(title, subtitle, app="os", tag=None):
    topbar(app, {"os": None, "ai": "Chat"}.get(app, "Overview"))
    tag_html = f"<div class='tag'>{tag}</div>" if tag else ""
    st.markdown(
        f"<div class='hero' style='background:{GRADIENTS[app]}'>{tag_html}"
        f"<h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def page_header(title, subtitle, app="os", icon="📄"):
    topbar(app, title)
    st.markdown(
        f"<div class='ph'><div class='ph-icon' style='background:{GRADIENTS[app]}'>{icon}</div>"
        f"<div><h1>{title}</h1><p>{subtitle}</p></div></div>",
        unsafe_allow_html=True,
    )


def stats(items):
    """A responsive row of small stat tiles from (label, value) pairs."""
    tiles = "".join(f"<div class='stat'><span>{escape(str(label))}</span><b>{escape(str(value))}</b></div>"
                    for label, value in items)
    st.markdown(f"<div class='stats'>{tiles}</div>", unsafe_allow_html=True)


def credits():
    st.markdown(f"<div class='credits'>{CREDITS}</div>", unsafe_allow_html=True)


def to_df(rows, columns=None):
    """DataFrame with MySQL DECIMAL values turned into normal numbers for charts."""
    df = pd.DataFrame(rows, columns=columns)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


def flash(message, icon="✅"):
    """Show a toast after the next rerun (toasts are lost when st.rerun() runs)."""
    st.session_state.flash = (message, icon)


def show_flash():
    if "flash" in st.session_state:
        message, icon = st.session_state.pop("flash")
        st.toast(message, icon=icon)


def sql_playground(examples, tables_help):
    """Pick an example query, edit it, and see the result (read-only)."""
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    i = c1.selectbox("Example", range(len(examples)),
                     format_func=lambda i: f"{i + 1}. {examples[i]['title']}")
    with c2.popover("Tables", icon=":material/table_chart:", width="stretch"):
        st.markdown(tables_help)
    example = examples[i]

    with card():
        st.info(example["explain"], icon=":material/lightbulb:")
        sql = st.text_area("SQL — edit it, then press ⌘/Ctrl + Enter to run", example["sql"],
                           height=210, key=f"sql_{example['app']}_{i}")
    try:
        columns, rows = db.run_select(sql)
        with card():
            st.caption(f"✅ {len(rows)} row(s)")
            st.dataframe(to_df(rows, columns), width="stretch", hide_index=True)
    except ValueError as e:
        st.warning(str(e))
    except mysql.connector.Error as e:
        st.error(f"SQL error: {e.msg}")
