import time

import mysql.connector
import streamlit as st

import ai
import auth
import shop
import ui

st.set_page_config(page_title="Stratex", page_icon="assets/icon.png", layout="wide")
st.logo("assets/logo.png", size="large")

SESSION_MINUTES = 30

if "user" not in st.session_state:
    st.session_state.user = None


def sign_out(message=None):
    st.session_state.user = None
    if message:
        ui.flash(message, "🔒")
    st.rerun()


DASHBOARD = st.Page(shop.dashboard, title="Dashboard", icon=":material/dashboard:", default=True)
NEW_ORDER = st.Page(shop.new_order, title="New order", icon=":material/add_shopping_cart:", url_path="new-order")
ORDERS = st.Page(shop.orders, title="Orders", icon=":material/receipt_long:", url_path="orders")
PAYMENTS = st.Page(shop.payments, title="Payments", icon=":material/payments:", url_path="payments")
PRODUCTS = st.Page(shop.products, title="Products", icon=":material/inventory_2:", url_path="products")
WAREHOUSE = st.Page(shop.warehouse, title="Warehouse", icon=":material/warehouse:", url_path="warehouse")
AI_PAGE = st.Page(ai.assistant_page, title="Nuera AI", icon=":material/auto_awesome:", url_path="ai")
ACCOUNT_PAGE = st.Page(auth.account_page, title="Account", icon=":material/person:", url_path="account")
SIGN_IN_PAGE = st.Page(auth.sign_in_page, title="Sign in", icon=":material/login:", default=True)


def main():
    user = st.session_state.user
    if user and time.time() - st.session_state.get("last_active", time.time()) > SESSION_MINUTES * 60:
        sign_out(f"Signed out after {SESSION_MINUTES} minutes of inactivity.")
    st.session_state.last_active = time.time()
    ui.show_flash()

    if not st.session_state.user:
        st.navigation([SIGN_IN_PAGE], position="hidden").run()
        return

    page = st.navigation({"Overview": [DASHBOARD], "Sales": [NEW_ORDER, ORDERS, PAYMENTS],
                          "Inventory": [PRODUCTS, WAREHOUSE], "Assistant": [AI_PAGE], "You": [ACCOUNT_PAGE]})
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.user['username']}**")
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            sign_out()
        st.caption(ui.CREDITS)
    page.run()


try:
    main()
except mysql.connector.Error as e:
    st.error("An error occurred. Could not connect to the database.")
