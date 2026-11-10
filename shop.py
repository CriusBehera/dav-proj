import pandas as pd
import streamlit as st

import db
import ui

STATUSES = ["pending", "shipped", "delivered", "cancelled"]
METHODS = ["upi", "card", "cash", "bank transfer"]
MONEY = st.column_config.NumberColumn(format="₹%.0f")


def inr(value):
    return f"₹{float(value):,.0f}"


def df(rows, columns=None):
    return ui.to_df(rows, columns)


def dashboard():
    ui.header("Dashboard", "Sales, payments and stock at a glance.")
    days = st.segmented_control("Period", [7, 30, 90], default=30,
                                format_func=lambda d: f"Last {d} days", key="period") or 30
    d = db.dashboard(days)
    boxes = st.columns(5)
    for box, (label, value) in zip(boxes, [
            ("Sales", inr(d["sales"])), ("Orders", d["orders"]), ("Collected", inr(d["paid"])),
            ("Outstanding", inr(d["sales"] - d["paid"])), ("Low stock items", d["low_stock"])]):
        box.metric(label, value, border=True)
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Sales per day", anchor=False)
        if d["per_day"]:
            st.bar_chart(df(d["per_day"]), x="day", y="sales", alt="Bar chart of sales per day")
        else:
            st.caption("No sales in this period.")
    with right, st.container(border=True):
        st.subheader("Top products", anchor=False)
        if d["top_products"]:
            st.bar_chart(df(d["top_products"]), x="name", y="sold", horizontal=True,
                         alt="Bar chart of units sold per product")
        else:
            st.caption("No sales in this period.")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Top customers", anchor=False)
        st.dataframe(df(d["top_customers"]), hide_index=True, column_config={"spent": MONEY},
                     alt="Top customers by amount spent")
    with right, st.container(border=True):
        st.subheader("Orders by status", anchor=False)
        st.dataframe(df(d["by_status"]), hide_index=True, alt="Number of orders for each status")
    st.caption(f"Stock value at cost: {inr(d['stock_value'])}")


def new_order():
    ui.header("New order", "Choose a customer and warehouse, then enter quantities.")
    customers, warehouses = db.get_customers(), db.get_warehouses()
    if not warehouses:
        st.info("Add a warehouse first on the Warehouse page.")
        return
    c1, c2 = st.columns(2)
    customer = c1.selectbox("Customer", customers, format_func=lambda c: c["name"])
    warehouse = c2.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"])
    with st.expander("Add a new customer"), st.form("customer", clear_on_submit=True, border=False):
        name = st.text_input("Name")
        email, phone = st.columns(2)
        email_value, phone_value = email.text_input("Email"), phone.text_input("Phone")
        if st.form_submit_button("Save customer") and name.strip():
            db.add_customer(name.strip(), email_value.strip(), phone_value.strip())
            st.rerun()
    if not customer:
        st.info("Add a customer to start an order.")
        return

    prices = {p["id"]: p["price"] for p in db.get_products()}
    lines = pd.DataFrame([{"id": r["product_id"], "Product": r["name"], "Price": float(prices[r["product_id"]]),
                           "In stock": r["qty"], "Quantity": 0}
                          for r in db.get_stock() if r["warehouse_id"] == warehouse["id"]])
    n = st.session_state.setdefault("order_n", 0)
    edited = st.data_editor(lines, hide_index=True, key=f"lines_{warehouse['id']}_{n}",
                            disabled=["id", "Product", "Price", "In stock"],
                            column_order=["Product", "Price", "In stock", "Quantity"],
                            column_config={"Price": MONEY, "Quantity": st.column_config.NumberColumn(
                                min_value=0, step=1)}, alt="Products and quantities for the new order")
    chosen = edited[edited["Quantity"] > 0]
    total = (chosen["Price"] * chosen["Quantity"]).sum()
    too_many = (chosen["Quantity"] > chosen["In stock"]).any()
    st.metric("Order total", inr(total))
    if too_many:
        st.error("One of the quantities is more than the stock in this warehouse.")
    if st.button("Place order", type="primary", icon=":material/shopping_cart_checkout:",
                 disabled=chosen.empty or too_many):
        items = [(int(r["id"]), int(r["Quantity"]), r["Price"]) for _, r in chosen.iterrows()]
        error = db.create_order(customer["id"], warehouse["id"], items, st.session_state.user["id"])
        if error:
            st.error(error)
        else:
            st.session_state.order_n = n + 1
            ui.flash(f"Order placed for {customer['name']}: {inr(total)}", "🧾")
            st.rerun()


def orders():
    ui.header("Orders", "All sales orders, their items and status.")
    status = st.segmented_control("Status", STATUSES, key="order_status")
    data = db.get_orders(status)
    if not data:
        st.info("No orders found.")
        return
    table = df(data)
    table["balance"] = table["total"] - table["paid"]
    st.dataframe(table, hide_index=True, alt="Sales orders",
                 column_config={"total": MONEY, "paid": MONEY, "balance": MONEY})
    order = st.selectbox("Open an order", data, format_func=lambda o: f"#{o['id']} · {o['customer']} · {inr(o['total'])}")
    with st.container(border=True):
        st.subheader(f"Order #{order['id']}", anchor=False)
        st.dataframe(df(db.get_order_items(order["id"])), hide_index=True, alt="Items in this order",
                     column_config={"unit_price": MONEY, "line_total": MONEY})
        new_status = st.segmented_control("Change status", STATUSES, default=order["status"],
                                          key=f"status_{order['id']}")
        if new_status and new_status != order["status"] and st.button("Save status", type="primary"):
            db.set_order_status(order["id"], new_status)
            ui.flash("Cancelled orders put their stock back." if new_status == "cancelled" else "Status saved", "✅")
            st.rerun()


def payments():
    ui.header("Payments", "Record money received and see what is still owed.")
    data = db.get_orders()
    live = [o for o in data if o["status"] != "cancelled"]
    owed = sum(o["total"] - o["paid"] for o in live)
    c1, c2, c3 = st.columns(3)
    c1.metric("Collected", inr(sum(o["paid"] for o in live)), border=True)
    c2.metric("Outstanding", inr(owed), border=True)
    c3.metric("Unpaid orders", sum(1 for o in live if o["total"] > o["paid"]), border=True)
    open_orders = [o for o in live if o["total"] > o["paid"]]
    with st.container(border=True):
        st.subheader("Record a payment", anchor=False)
        if not open_orders:
            st.success("Everything is paid.")
        else:
            order = st.selectbox("Order", open_orders, format_func=lambda o: (
                f"#{o['id']} · {o['customer']} · balance {inr(o['total'] - o['paid'])}"))
            balance = float(order["total"] - order["paid"])
            with st.form("payment", border=False):
                amount = st.number_input("Amount (₹)", min_value=1.0, max_value=balance, value=balance, step=100.0)
                method = st.selectbox("Method", METHODS)
                note = st.text_input("Note (optional)")
                if st.form_submit_button("Save payment", type="primary"):
                    error = db.add_payment(order["id"], amount, method, note)
                    if error:
                        st.error(error)
                    else:
                        ui.flash(f"Payment of {inr(amount)} saved", "💰")
                        st.rerun()
    st.subheader("Payment history", anchor=False)
    st.dataframe(df(db.get_payments()), hide_index=True, alt="Payments received",
                 column_config={"amount": MONEY})


def products():
    ui.header("Products", "Your catalogue. Prices and reorder levels can be edited in the table.")
    search = st.text_input("Search", placeholder="Name, SKU or category", label_visibility="collapsed")
    data = df(db.get_products(search))
    if data.empty:
        st.info("No products found.")
    else:
        for col in ("price", "cost"):
            data[col] = data[col].astype(float)
        edited = st.data_editor(data, hide_index=True, key="products_table",
                                disabled=["id", "sku", "in_stock"], alt="Product catalogue",
                                column_config={"price": MONEY, "cost": MONEY})
        if st.button("Save changes", icon=":material/save:") and not edited.equals(data):
            for _, r in edited.iterrows():
                db.update_product(int(r["id"]), r["name"], r["category"], r["price"], r["cost"],
                                  int(r["reorder_level"]))
            ui.flash("Products updated", "✅")
            st.rerun()
        remove = st.selectbox("Delete a product", [None] + data.to_dict("records"),
                              format_func=lambda p: "Choose…" if p is None else f"{p['sku']} · {p['name']}")
        if remove and st.button("Delete product", icon=":material/delete:"):
            error = db.delete_product(remove["id"])
            if error:
                st.error(error)
            else:
                st.rerun()
    with st.expander("Add a product"), st.form("product", clear_on_submit=True, border=False):
        a, b = st.columns(2)
        sku, name = a.text_input("SKU"), b.text_input("Name")
        category = a.text_input("Category")
        reorder = b.number_input("Reorder level", min_value=0, value=10, step=1)
        price = a.number_input("Price (₹)", min_value=0.0, step=50.0)
        cost = b.number_input("Cost (₹)", min_value=0.0, step=50.0)
        if st.form_submit_button("Add product", type="primary"):
            if not sku.strip() or not name.strip():
                st.error("SKU and name are required.")
            else:
                error = db.add_product(sku.strip(), name.strip(), category.strip(), price, cost, reorder)
                if error:
                    st.error(error)
                else:
                    ui.flash("Product added", "📦")
                    st.rerun()


def warehouse():
    ui.header("Warehouse", "Stock in each warehouse, deliveries in and transfers between them.")
    warehouses, rows = db.get_warehouses(), db.get_stock()
    if rows:
        stock = df(rows).pivot_table(index=["product_id", "name", "reorder_level"], columns="warehouse",
                                     values="qty", aggfunc="sum").reset_index()
        names = [w["name"] for w in warehouses]
        stock["Total"] = stock[names].sum(axis=1)
        stock["Status"] = ["Low" if t <= r else "OK" for t, r in zip(stock["Total"], stock["reorder_level"])]
        c1, c2, c3 = st.columns(3)
        c1.metric("Warehouses", len(warehouses), border=True)
        c2.metric("Units in stock", int(stock["Total"].sum()), border=True)
        c3.metric("Products low on stock", int((stock["Status"] == "Low").sum()), border=True)
        st.dataframe(stock.drop(columns=["product_id"]).rename(columns={"name": "Product", "reorder_level": "Reorder at"}),
                     hide_index=True, alt="Stock of every product in each warehouse")
    products = db.get_products()
    receive, transfer, add = st.tabs(["Receive stock", "Transfer", "Add warehouse"])
    with receive, st.form("receive", border=False):
        product = st.selectbox("Product", products, format_func=lambda p: p["name"])
        where = st.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"])
        qty = st.number_input("Units received (use a minus number to remove)", value=10, step=1)
        if st.form_submit_button("Update stock", type="primary") and product and where and qty:
            db.change_stock(product["id"], where["id"], int(qty))
            ui.flash("Stock updated", "📦")
            st.rerun()
    with transfer, st.form("transfer", border=False):
        product = st.selectbox("Product", products, format_func=lambda p: p["name"], key="t_product")
        a, b = st.columns(2)
        source = a.selectbox("From", warehouses, format_func=lambda w: w["name"], key="t_from")
        target = b.selectbox("To", warehouses, format_func=lambda w: w["name"], key="t_to")
        qty = st.number_input("Units", min_value=1, value=1, step=1)
        if st.form_submit_button("Transfer", type="primary"):
            if source == target:
                st.error("Choose two different warehouses.")
            else:
                error = db.transfer_stock(product["id"], source["id"], target["id"], int(qty))
                if error:
                    st.error(error)
                else:
                    ui.flash("Stock transferred", "🚚")
                    st.rerun()
    with add, st.form("new_warehouse", clear_on_submit=True, border=False):
        name, place = st.text_input("Name"), st.text_input("Location")
        if st.form_submit_button("Add warehouse", type="primary") and name.strip():
            error = db.add_warehouse(name.strip(), place.strip())
            if error:
                st.error(error)
            else:
                st.rerun()
