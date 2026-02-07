from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, send_from_directory
)
from datetime import datetime, timezone
import os
import uuid
from dotenv import load_dotenv

# 🔥 Firebase helpers
from firebase_config import (
    get_menu,
    save_order,
    get_all_orders,
    get_db,
    send_push_to_admins
)


# ------------------ ENV ------------------
load_dotenv()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# ------------------ APP INIT ------------------
app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = 3600
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # HTTPS only in prod

# ------------------ CONTEXT ------------------
@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return {
        "now": datetime.now(timezone.utc),
        "cart_count": sum(cart.values())
    }

# ------------------ FALLBACK MENU ------------------
SAMPLE_MENU = [
    {"id": "1", "name": "Masala Chai", "price": 20, "category": "Tea"},
    {"id": "2", "name": "Green Tea", "price": 25, "category": "Tea"},
    {"id": "3", "name": "Coffee", "price": 30, "category": "Coffee"},
]

# ------------------ HOME ------------------
@app.route("/")
def index():
    try:
        menu_items = get_menu()
        if not menu_items:
            raise Exception("Empty menu from Firestore")
    except Exception as e:
        print("❌ get_menu failed, using SAMPLE_MENU:", e)
        menu_items = SAMPLE_MENU

    menu_by_category = {}
    for item in menu_items:
        menu_by_category.setdefault(
            item.get("category", "Others"), []
        ).append(item)

    return render_template(
        "index.html",
        menu_by_category=menu_by_category
    )

# ------------------ CART ------------------
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    session.setdefault("cart", {})

    item_id = request.form.get("item_id")
    qty = int(request.form.get("quantity", 1))

    if not item_id:
        return jsonify({"status": "error"}), 400

    session["cart"][item_id] = session["cart"].get(item_id, 0) + qty
    session.modified = True

    return jsonify({
        "status": "success",
        "cart_count": sum(session["cart"].values())
    })

@app.route("/cart")
def view_cart():
    cart = session.get("cart", {})
    cart_items = []
    total = 0

    menu_lookup = {i["id"]: i for i in SAMPLE_MENU}

    for item_id, qty in cart.items():
        if item_id not in menu_lookup:
            continue

        item = menu_lookup[item_id]
        item_total = item["price"] * qty
        total += item_total

        cart_items.append({
            "id": item_id,
            "name": item["name"],
            "price": item["price"],
            "quantity": qty,
            "total": item_total
        })

    return render_template("cart.html", cart_items=cart_items, total=total)

@app.route("/update_cart", methods=["POST"])
def update_cart():
    item_id = request.form.get("item_id")
    change = int(request.form.get("change", 0))

    if "cart" not in session or item_id not in session["cart"]:
        return jsonify({"status": "error"})

    session["cart"][item_id] += change
    if session["cart"][item_id] <= 0:
        session["cart"].pop(item_id)

    session.modified = True
    return jsonify({"status": "success"})

@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():
    item_id = request.form.get("item_id")
    session.get("cart", {}).pop(item_id, None)
    session.modified = True
    return jsonify({"status": "success"})

# ------------------ CREATE ORDER ------------------
@app.route("/create_order", methods=["POST"])
def create_order_route():
    cart = session.get("cart")

    print("🛒 CART CONTENT:", cart)  # DEBUG

    if not cart:
        print("❌ Cart empty, redirecting back")
        return redirect(url_for("cart"))

    # ✅ CREATE ORDER CODE
    order_code = str(uuid.uuid4())[:8].upper()

    items = []
    total = 0

    for item_id, qty in cart.items():
        item = next((i for i in SAMPLE_MENU if i["id"] == item_id), None)
        if not item:
            continue

        item_total = item["price"] * qty
        total += item_total

        items.append({
            "name": item["name"],
            "price": item["price"],
            "quantity": qty,
            "total": item_total
        })

    order_data = {
        "orderId": order_code,
        "items": items,
        "totalAmount": total,
        "orderStatus": "OPEN",
        "paymentStatus": "PENDING",
        "createdAt": datetime.now(timezone.utc)
    }

    # ✅ SAVE ORDER
    order_id = save_order(order_data)
    print("🧾 ORDER CREATED:", order_id)

    if not order_id:
        print("❌ Order save failed")
        return redirect(url_for("cart"))

    # ✅ STORE PAYMENT DATA IN SESSION
    session["pending_payment"] = {
        "order_id": order_id,
        "order_code": order_code,
        "total": total
    }

    # ✅ CLEAR CART
    session.pop("cart", None)
    session.modified = True

    # ✅ REDIRECT TO PAYMENT PAGE
    return redirect(url_for("payment"))


@app.route("/order/success")
def order_success():
    data = session.get("pending_payment")

    if not data:
        return redirect(url_for("index"))

    return render_template(
        "success.html",
        total=data["total"],
        order_code=data["order_code"]
    )


# ------------------ PAYMENT (NO FIRESTORE) ------------------
@app.route("/payment")
def payment():
    data = session.get("pending_payment")
    if not data:
        return redirect(url_for("index"))

    upi_id = "yourstore@upi"
    payee_name = "Vijeta Cafe"
    amount = data["total"]

    upi_link = (
        f"upi://pay?"
        f"pa={upi_id}&pn={payee_name}"
        f"&am={amount}&cu=INR"
        f"&tn=Order%20{data['order_code']}"
    )

    return render_template(
        "payment.html",
        order=data,
        upi_link=upi_link,
        upi_id=upi_id
    )

# ------------------ CONFIRM PAYMENT ------------------
@app.route("/order/confirm_payment", methods=["POST"])
def confirm_payment():
    data = session.get("pending_payment")
    if not data:
        return redirect(url_for("index"))

    db = get_db()
    db.collection("orders").document(data["order_id"]).update({
        "orderStatus": "PAID",
        "paymentStatus": "PAID",
        "updatedAt": datetime.now(timezone.utc)
    })

    session.pop("pending_payment", None)
    session["last_order_id"] = data["order_id"]
    session.modified = True

    return redirect(url_for("order_success"))



# ------------------ ADMIN ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("email") == ADMIN_EMAIL:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    return render_template("admin_dashboard.html")

@app.route("/admin/orders/live")
def admin_live_orders():
    if not session.get("admin"):
        return jsonify([])

    try:
        orders = get_all_orders()
        return jsonify(orders)

    except Exception as e:
        print("❌ admin_live_orders error:", e)
        return jsonify([])



@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

# ------------------ STATIC ------------------
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route("/firebase-messaging-sw.js")
def firebase_sw():
    return app.send_static_file("firebase-messaging-sw.js")

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)

