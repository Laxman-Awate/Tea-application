from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, send_from_directory,
    flash
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
    # Snacks
    {"id": "1", "name": "Biscuit", "price": 5, "category": "Snacks"},
    {"id": "2", "name": "Cake", "price": 5, "category": "Snacks"},

    # Beverages
    {"id": "3", "name": "Masala Tea", "price": 10, "category": "Beverages"},
    {"id": "4", "name": "Jaggery Tea", "price": 20, "category": "Beverages"},
    {"id": "5", "name": "Lemon Tea", "price": 15, "category": "Beverages"},
    {"id": "6", "name": "Black Tea", "price": 15, "category": "Beverages"},
    {"id": "7", "name": "Green Tea", "price": 15, "category": "Beverages"},
    {"id": "8", "name": "Lemon Ice Tea", "price": 40, "category": "Beverages"},
    {"id": "9", "name": "Sugarless Tea", "price": 15, "category": "Beverages"},
    {"id": "10", "name": "Hot Coffee", "price": 20, "category": "Beverages"},
    {"id": "11", "name": "Cold Coffee", "price": 50, "category": "Beverages"},
    {"id": "12", "name": "Boost", "price": 20, "category": "Beverages"},
    {"id": "13", "name": "Bournvita", "price": 20, "category": "Beverages"},
    {"id": "14", "name": "Milk", "price": 15, "category": "Beverages"},
    {"id": "15", "name": "Badam Milk", "price": 20, "category": "Beverages"},

    # Sandwiches
    {"id": "16", "name": "Veg Sandwich", "price": 40, "category": "Sandwiches"},
    {"id": "17", "name": "Veg Grilled Sandwich", "price": 60, "category": "Sandwiches"},
    {"id": "18", "name": "Cheese Grilled Sandwich", "price": 70, "category": "Sandwiches"},
    {"id": "19", "name": "Paneer Cheese Grilled Sandwich", "price": 80, "category": "Sandwiches"},
    {"id": "20", "name": "Cheese Corn Grilled Sandwich", "price": 80, "category": "Sandwiches"},

    # Momos
    {"id": "21", "name": "Kurkure Momos", "price": 100, "category": "Momos"},
    {"id": "22", "name": "Peri Peri Momos", "price": 80, "category": "Momos"},
    {"id": "23", "name": "Paneer Momos", "price": 80, "category": "Momos"},
    {"id": "24", "name": "Schezwan Momos", "price": 80, "category": "Momos"},
    {"id": "25", "name": "Mix Veggie Momos", "price": 70, "category": "Momos"},
    {"id": "26", "name": "Corn Momos", "price": 70, "category": "Momos"},

    # Maggi
    {"id": "27", "name": "Plain Maggi", "price": 35, "category": "Maggi"},
    {"id": "28", "name": "Veg Maggi", "price": 45, "category": "Maggi"},
    {"id": "29", "name": "Egg Maggi", "price": 55, "category": "Maggi"},
    {"id": "30", "name": "Cheese Maggi", "price": 55, "category": "Maggi"},

    # Fries
    {"id": "31", "name": "French Fries", "price": 60, "category": "Fries"},
    {"id": "32", "name": "Peri Peri Fries", "price": 70, "category": "Fries"},
    {"id": "33", "name": "Cheese French Fries", "price": 80, "category": "Fries"},

    # Frankie
    {"id": "34", "name": "Paneer Cheese Frankie", "price": 80, "category": "Frankie"},
    {"id": "35", "name": "Cheese Frankie", "price": 70, "category": "Frankie"},
    {"id": "36", "name": "Veg Frankie", "price": 60, "category": "Frankie"},
    {"id": "37", "name": "Corn Frankie", "price": 70, "category": "Frankie"},
    {"id": "38", "name": "Aloo Frankie", "price": 60, "category": "Frankie"}
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

    # Get customer name from form
    print("🔍 Form data received:", dict(request.form))  # DEBUG
    customer_name = request.form.get("customerName", "").strip()
    print("🔍 Customer name extracted:", repr(customer_name))  # DEBUG
    if not customer_name or len(customer_name) < 2:
        print("❌ Invalid customer name")
        flash("Please enter your name (at least 2 characters)", "error")
        return redirect(url_for("view_cart"))

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
        "customerName": customer_name,  # Add customer name
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
    
    today_date = datetime.now().strftime("%B %d, %Y")  # e.g., "February 20, 2026"
    return render_template("admin_dashboard.html", today_date=today_date)

@app.route("/admin/orders/live")
def admin_live_orders():
    if not session.get("admin"):
        return jsonify([])

    try:
        orders = get_all_orders()
        
        # Filter orders for today only
        today = datetime.now().date().isoformat()
        today_orders = []
        
        for order in orders:
            if order.get("createdAt"):
                # Handle Firebase timestamp
                if hasattr(order["createdAt"], "seconds"):
                    order_date = datetime.fromtimestamp(order["createdAt"].seconds).date().isoformat()
                else:
                    order_date = datetime.fromisoformat(str(order["createdAt"]).split("T")[0]).date().isoformat()
                
                if order_date == today:
                    today_orders.append(order)
        
        return jsonify(today_orders)

    except Exception as e:
        print("❌ admin_live_orders error:", e)
        return jsonify([])


@app.route("/admin/orders/all")
def admin_all_orders():
    if not session.get("admin"):
        return jsonify([])

    try:
        orders = get_all_orders()
        return jsonify(orders)

    except Exception as e:
        print("❌ admin_all_orders error:", e)
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

