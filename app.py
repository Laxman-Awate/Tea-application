from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, send_from_directory,
    flash
)
from datetime import datetime, timezone
import os
import uuid
from dotenv import load_dotenv
import json

# 🔥 Firebase helpers
from firebase_config import (
    get_menu,
    save_order,
    get_all_orders,
    get_db,
    send_push_to_admins
)

# 🔐 Payment system (with fallback)
try:
    from payment_gateway import payment_gateway
    from transaction_manager import transaction_manager
    from payment_middleware import (
        require_payment_verified,
        validate_payment_session,
        rate_limit_payment_attempts,
        validate_payment_payload,
        secure_transaction_access,
        log_payment_activity
    )
    from security_handlers import (
        error_handler,
        duplicate_prevention,
        network_handler,
        security_validator
    )
    PAYMENT_SYSTEM_AVAILABLE = True
    print("✅ Payment system loaded successfully")
except ImportError as e:
    print(f"⚠️ Payment system not available: {e}")
    PAYMENT_SYSTEM_AVAILABLE = False
    
    # Fallback decorators
    def require_payment_verified(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    
    def validate_payment_session(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    
    def rate_limit_payment_attempts(max_attempts=5, window_minutes=15):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def validate_payment_payload(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    
    def secure_transaction_access(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    
    def log_payment_activity(activity_type):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function
        return decorator

import secrets
from functools import wraps


# ------------------ ENV ------------------
from dotenv import load_dotenv, find_dotenv

# Clear system environment variable first
if 'ADMIN_EMAIL' in os.environ:
    del os.environ['ADMIN_EMAIL']
    print("🗑️ Cleared system ADMIN_EMAIL")

# Force load .env from current directory
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)  # Override system vars
    print(f"📁 Loading .env from: {dotenv_path}")
else:
    print("❌ .env file not found!")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "anjaneykamble5@gmail.com")  # Fallback to your email
print(f"🔐 Admin email loaded: {ADMIN_EMAIL}")  # Debug line
# ------------------ APP INIT ------------------
app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# Serverless-compatible session configuration
if os.environ.get("VERCEL"):  # Check if running on Vercel
    # Use client-side sessions for serverless (no filesystem)
    app.config["SESSION_TYPE"] = "null"
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_USE_SIGNER"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    print("🌐 Running on Vercel - client-side session mode")
else:
    # Local development
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["PERMANENT_SESSION_LIFETIME"] = 3600
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False  # HTTPS only in prod
    print("💻 Running locally - standard session mode")

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
    try:
        item_id = request.form.get("item_id")
        quantity = int(request.form.get("quantity", 1))
        
        print(f"🛒 Add to cart: item_id={item_id}, quantity={quantity}")
        print(f"🔍 Session before: {dict(session)}")
        
        if not item_id:
            print("❌ No item_id provided")
            return jsonify({"success": False, "error": "No item ID"})
        
        # Initialize cart if not exists
        if "cart" not in session:
            session["cart"] = {}
            print("🛒 Initialized new cart")
        
        # Add/update item
        current_qty = session["cart"].get(item_id, 0)
        session["cart"][item_id] = current_qty + quantity
        session.modified = True
        
        print(f"✅ Cart updated: {session['cart']}")
        print(f"🔍 Session after: {dict(session)}")
        
        return jsonify({
            "success": True,
            "cart_count": sum(session["cart"].values()),
            "message": f"Added {quantity} item(s) to cart"
        })
        
    except Exception as e:
        print(f"❌ Add to cart error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to add item to cart"
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
    customer_email = request.form.get("customerEmail", "").strip()
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
        "customerName": customer_name,
        "customerEmail": customer_email,
        "items": items,
        "totalAmount": total,
        "orderStatus": "PENDING_PAYMENT",
        "paymentStatus": "PENDING",
        "createdAt": datetime.now(timezone.utc)
    }

    # ✅ SAVE ORDER
    print("🔥 Attempting to save order...")
    order_id = save_order(order_data)
    print("🧾 ORDER CREATED:", order_id)

    if not order_id:
        print("❌ Order save failed - Firebase issue")
        flash("Unable to save order. Please try again.", "error")
        return redirect(url_for("view_cart"))

    # ✅ CREATE TRANSACTION (if payment system available)
    if PAYMENT_SYSTEM_AVAILABLE:
        try:
            transaction = transaction_manager.create_transaction(
                order_id=order_id,
                amount=total,
                customer_name=customer_name,
                customer_email=customer_email
            )
            print("🔐 TRANSACTION CREATED:", transaction["transaction_id"])
            
            # Store transaction info in session
            transaction_info = {
                "transaction_id": transaction["transaction_id"],
                "security_token": transaction["security_token"]
            }
        except Exception as e:
            print("❌ Transaction creation failed:", e)
            transaction_info = {}
    else:
        print("⚠️ Using simple payment flow (no transaction system)")
        transaction_info = {}

    # ✅ STORE PAYMENT DATA IN SESSION
    session["pending_payment"] = {
        "order_id": order_id,
        "order_code": order_code,
        "total": total,
        **transaction_info
    }

    # ✅ CLEAR CART
    session.pop("cart", None)
    session.modified = True

    # ✅ REDIRECT TO PAYMENT PAGE
    return redirect(url_for("payment"))


@app.route("/order/success")
def order_success():
    """Success page - works with both payment systems"""
    data = session.get("pending_payment")

    if not data:
        # Try to get last order from session
        last_order_id = session.get("last_order_id")
        if last_order_id:
            try:
                db = get_db()
                order_doc = db.collection("orders").document(last_order_id).get()
                if order_doc.exists:
                    order_data = order_doc.to_dict()
                    return render_template(
                        "success.html",
                        total=order_data.get("totalAmount", 0),
                        order_code=order_data.get("orderId", "Unknown")
                    )
            except Exception as e:
                print(f"❌ Failed to get last order: {e}")
        
        # If no data available, redirect to home
        return redirect(url_for("index"))

    return render_template(
        "success.html",
        total=data["total"],
        order_code=data["order_code"]
    )


# ------------------ PAYMENT ------------------
@app.route("/payment")
@validate_payment_session
def payment():
    """Secure payment page with transaction validation"""
    data = session.get("pending_payment")
    if not data:
        return redirect(url_for("index"))

    # If payment system is not available, use simple payment flow
    if not PAYMENT_SYSTEM_AVAILABLE:
        print("⚠️ Using simple payment template")
        return render_template("payment.html", order=data)

    # Verify transaction exists and is valid
    transaction_id = data.get("transaction_id")
    if transaction_id:
        transaction = transaction_manager.get_transaction(transaction_id)
        
        if not transaction:
            flash("Invalid payment session. Please try again.", "error")
            return redirect(url_for("index"))
        
        # Check if transaction is expired
        if transaction.get("status") == "EXPIRED":
            flash("Payment session expired. Please try again.", "error")
            return redirect(url_for("index"))
        
        # Check if transaction is already completed
        if transaction.get("status") == "SUCCESS":
            return redirect(url_for("order_success"))

        # Create payment order with gateway
        try:
            order_result = payment_gateway.create_order(
                amount=data["total"],
                receipt=data["order_code"]
            )
            
            if not order_result["success"]:
                flash("Unable to initiate payment. Please try again.", "error")
                return redirect(url_for("index"))
            
            gateway_order = order_result["order"]
            
            # Update transaction with gateway order ID
            transaction_manager.update_transaction_status(
                data["transaction_id"],
                "PROCESSING",
                gateway_order_id=gateway_order["id"]
            )
            
        except Exception as e:
            print(f"❌ Payment order creation failed: {e}")
            flash("Payment initialization failed. Please try again.", "error")
            return redirect(url_for("index"))

        # UPI payment details
        upi_id = "q391330410@ybl"
        payee_name = "Vijeta Cafe"
        amount = data["total"]
        order_code = data["order_code"]

        # UPI payment link
        upi_link = (
            f"upi://pay?"
            f"pa={upi_id}&pn={payee_name}"
            f"&am={amount}&cu=INR"
            f"&tn=Order%20{order_code}"
        )

        return render_template(
            "secure_payment.html",
            order=data,
            transaction=transaction,
            gateway_order=gateway_order,
            upi_link=upi_link,
            upi_id=upi_id,
            gateway_key=order_result["razorpay_key"]
        )
    
    else:
        # Fallback to simple payment
        return render_template("payment.html", order=data)


# ------------------ SIMPLE PAYMENT CONFIRMATION (Fallback) ------------------
@app.route("/order/confirm_payment", methods=["POST"])
def confirm_payment():
    """Simple payment confirmation for fallback mode"""
    data = session.get("pending_payment")
    if not data:
        return redirect(url_for("index"))

    # Update order status to confirmed
    try:
        db = get_db()
        db.collection("orders").document(data["order_id"]).update({
            "orderStatus": "CONFIRMED",
            "paymentStatus": "PAID",
            "paymentVerifiedAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
            "paymentMethod": "SIMPLE_UPI"
        })
        print("✅ Order confirmed with simple payment")
    except Exception as e:
        print(f"❌ Failed to update order: {e}")

    # Clear pending payment and store last order
    session.pop("pending_payment", None)
    session["last_order_id"] = data["order_id"]
    session.modified = True

    # Redirect to success
    return redirect(url_for("order_success"))

# ------------------ SECURE PAYMENT VERIFICATION ------------------
@app.route("/payment/verify", methods=["POST"])
@rate_limit_payment_attempts(max_attempts=5, window_minutes=15)
@validate_payment_payload
@log_payment_activity("payment_verification")
def verify_payment():
    """Secure payment verification endpoint with enhanced security"""
    try:
        payment_data = request.validated_payment_data
        pending_payment = session.get("pending_payment")
        
        if not pending_payment:
            return jsonify(error_handler.handle_payment_error("SESSION_EXPIRED")), 400
        
        # Check for duplicate payments
        if duplicate_prevention.is_duplicate_payment(
            pending_payment["order_id"], 
            payment_data["payment_id"]
        ):
            return jsonify({
                "success": False,
                "error": "Duplicate payment detected",
                "code": "DUPLICATE_PAYMENT",
                "user_message": "Payment already processed. Please check your order status."
            }), 400
        
        # Verify transaction access
        verification = transaction_manager.verify_transaction_access(
            pending_payment["transaction_id"],
            pending_payment["security_token"],
            request
        )
        
        if not verification["valid"]:
            return jsonify(error_handler.handle_payment_error("TRANSACTION_NOT_FOUND")), 403
        
        transaction = verification["transaction"]
        
        # Check transaction status
        if transaction.get("status") not in ["INITIATED", "PROCESSING"]:
            return jsonify({
                "success": False,
                "error": f"Transaction already {transaction.get('status').lower()}",
                "code": "INVALID_TRANSACTION_STATE",
                "user_message": f"Transaction is already {transaction.get('status').lower()}."
            }), 400
        
        # Verify payment signature with network failure handling
        try:
            signature_valid = payment_gateway.verify_payment_signature(
                payment_data["order_id"],
                payment_data["payment_id"],
                payment_data["signature"]
            )
        except Exception as e:
            error_response = network_handler.handle_payment_gateway_failure(
                e, transaction["transaction_id"]
            )
            return jsonify(error_response), 500
        
        if not signature_valid:
            return jsonify(error_handler.handle_payment_error("INVALID_SIGNATURE")), 400
        
        # Record payment attempt
        try:
            transaction_manager.record_payment_attempt(
                transaction["transaction_id"],
                payment_data,
                request
            )
        except Exception as e:
            print(f"❌ Failed to record payment attempt: {e}")
        
        # Capture payment with retry logic
        try:
            capture_result = network_handler.with_retry(max_retries=2)(
                payment_gateway.capture_payment
            )(payment_data["payment_id"], pending_payment["total"])
        except Exception as e:
            error_response = network_handler.handle_payment_gateway_failure(
                e, transaction["transaction_id"]
            )
            
            # Update transaction as failed
            try:
                transaction_manager.update_transaction_status(
                    transaction["transaction_id"],
                    "FAILED",
                    gateway_payment_id=payment_data["payment_id"],
                    gateway_signature=payment_data["signature"],
                    error_message=str(e)
                )
            except Exception as update_error:
                print(f"❌ Failed to update transaction status: {update_error}")
            
            return jsonify(error_response), 500
        
        if not capture_result["success"]:
            # Update transaction as failed
            try:
                transaction_manager.update_transaction_status(
                    transaction["transaction_id"],
                    "FAILED",
                    gateway_payment_id=payment_data["payment_id"],
                    gateway_signature=payment_data["signature"],
                    error_message=capture_result["error"]
                )
            except Exception as e:
                print(f"❌ Failed to update transaction status: {e}")
            
            return jsonify(error_handler.handle_payment_error(
                "PAYMENT_FAILED",
                details=capture_result["error"]
            )), 400
        
        # Update transaction as successful
        try:
            updated_transaction = transaction_manager.update_transaction_status(
                transaction["transaction_id"],
                "SUCCESS",
                gateway_payment_id=payment_data["payment_id"],
                gateway_signature=payment_data["signature"],
                payment_captured=True
            )
        except Exception as e:
            print(f"❌ Failed to update transaction to success: {e}")
            # Continue anyway since payment was captured
        
        # Update order status
        try:
            db = get_db()
            db.collection("orders").document(pending_payment["order_id"]).update({
                "orderStatus": "CONFIRMED",
                "paymentStatus": "PAID",
                "paymentVerifiedAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                "gatewayPaymentId": payment_data["payment_id"]
            })
        except Exception as e:
            print(f"❌ Failed to update order status: {e}")
            # Continue anyway since payment was successful
        
        # Set verified payment session
        session["verified_payment"] = {
            "transaction_id": transaction["transaction_id"],
            "security_token": transaction["security_token"],
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "payment_id": payment_data["payment_id"]
        }
        
        # Clear pending payment
        session.pop("pending_payment", None)
        session.modified = True
        
        return jsonify({
            "success": True,
            "message": "Payment verified successfully",
            "redirect_to": url_for("order_success"),
            "transaction_id": transaction["transaction_id"]
        })
        
    except Exception as e:
        print(f"❌ Payment verification error: {e}")
        return jsonify(error_handler.handle_payment_error(
            "PAYMENT_FAILED",
            details=str(e)
        )), 500


# ------------------ PAYMENT STATUS CHECK ------------------
@app.route("/api/payment_status/<transaction_id>")
@secure_transaction_access
def check_payment_status(transaction_id):
    """Check payment status with security validation"""
    try:
        transaction = request.current_transaction
        
        # Get payment status from gateway
        if transaction.get("gateway_payment_id"):
            status_result = payment_gateway.get_payment_status(
                transaction["gateway_payment_id"]
            )
            
            if status_result["success"]:
                return jsonify({
                    "success": True,
                    "status": status_result["status"],
                    "transaction": {
                        "transaction_id": transaction["transaction_id"],
                        "order_id": transaction["order_id"],
                        "amount": transaction["amount"],
                        "status": transaction["status"],
                        "created_at": transaction["created_at"].isoformat() if transaction.get("created_at") else None
                    }
                })
        
        # Fallback to transaction status
        return jsonify({
            "success": True,
            "status": transaction.get("status", "UNKNOWN"),
            "transaction": {
                "transaction_id": transaction["transaction_id"],
                "order_id": transaction["order_id"],
                "amount": transaction["amount"],
                "status": transaction.get("status", "UNKNOWN"),
                "created_at": transaction["created_at"].isoformat() if transaction.get("created_at") else None
            }
        })
        
    except Exception as e:
        print(f"❌ Payment status check error: {e}")
        return jsonify({
            "success": False,
            "error": "Unable to check payment status"
        }), 500


# ------------------ PAYMENT RETRY ------------------
@app.route("/payment/retry/<transaction_id>", methods=["POST"])
@secure_transaction_access
@rate_limit_payment_attempts(max_attempts=3, window_minutes=10)
def retry_payment(transaction_id):
    """Retry failed payment with security checks"""
    try:
        transaction = request.current_transaction
        
        # Check if retry is allowed
        if transaction.get("status") not in ["FAILED", "CANCELLED"]:
            return jsonify({
                "success": False,
                "error": "Retry not allowed for this transaction"
            }), 400
        
        # Check retry limit
        if transaction.get("retry_count", 0) >= transaction.get("max_retries", 3):
            return jsonify({
                "success": False,
                "error": "Maximum retry attempts exceeded"
            }), 429
        
        # Reset transaction to initiated
        updated_transaction = transaction_manager.update_transaction_status(
            transaction_id,
            "INITIATED"
        )
        
        # Create new payment order
        order_result = payment_gateway.create_order(
            amount=transaction["amount"],
            receipt=f"retry_{transaction['order_id']}"
        )
        
        if not order_result["success"]:
            return jsonify({
                "success": False,
                "error": "Unable to create retry payment order"
            }), 500
        
        return jsonify({
            "success": True,
            "message": "Payment retry initiated",
            "gateway_order": order_result["order"],
            "gateway_key": order_result["razorpay_key"]
        })
        
    except Exception as e:
        print(f"❌ Payment retry error: {e}")
        return jsonify({
            "success": False,
            "error": "Payment retry failed"
        }), 500



# ------------------ ADMIN ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("email") == ADMIN_EMAIL:
            print(f"🔑 Login attempt: {request.form.get('email')}")
            print(f"✅ Expected: {ADMIN_EMAIL}")
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/approve_payment/<order_id>", methods=["POST"])
def admin_approve_payment(order_id):
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"})
    
    db = get_db()
    order_doc = db.collection("orders").document(order_id).get()
    
    if not order_doc.exists:
        return jsonify({"success": False, "error": "Order not found"})
    
    # Update order to PAID
    db.collection("orders").document(order_id).update({
        "orderStatus": "PAID",
        "paymentStatus": "PAID",
        "paymentVerifiedAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc)
    })
    
    return jsonify({"success": True})

@app.route("/admin/reject_payment/<order_id>", methods=["POST"])
def admin_reject_payment(order_id):
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"})
    
    db = get_db()
    order_doc = db.collection("orders").document(order_id).get()
    
    if not order_doc.exists:
        return jsonify({"success": False, "error": "Order not found"})
    
    # Update order to REJECTED
    db.collection("orders").document(order_id).update({
        "orderStatus": "PAYMENT_REJECTED",
        "paymentStatus": "REJECTED",
        "paymentRejectedAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc)
    })
    
    return jsonify({"success": True})

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

# ------------------ OFFLINE PAGE ------------------
@app.route("/offline")
def offline():
    return render_template("offline.html")

# ------------------ STATIC ------------------
@app.route("/test")
def test_interface():
    """Test interface for payment system"""
    if os.environ.get("FLASK_ENV") != "development":
        return redirect(url_for("index"))
    
    return send_from_directory(".", "test_interface.html")

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route("/firebase-messaging-sw.js")
def firebase_sw():
    return app.send_static_file("firebase-messaging-sw.js")

# ------------------ RUN ------------------
if __name__ == "__main__":
    # Set development environment for testing
    os.environ["FLASK_ENV"] = "development"
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))

# ------------------ TEST MODE ENDPOINTS ------------------
@app.route("/test/simulate_payment/<transaction_id>", methods=["POST"])
def test_simulate_payment(transaction_id):
    """Test endpoint to simulate successful payment"""
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"success": False, "error": "Test mode not available"}), 403
    
    try:
        # Get transaction
        transaction = transaction_manager.get_transaction(transaction_id)
        if not transaction:
            return jsonify({"success": False, "error": "Transaction not found"}), 404
        
        # Generate mock payment data
        mock_payment_id = f"pay_test_{secrets.token_hex(8)}"
        mock_signature = secrets.token_hex(32)
        
        # Simulate payment verification
        payment_data = {
            "order_id": transaction.get("gateway_order_id"),
            "payment_id": mock_payment_id,
            "signature": mock_signature
        }
        
        # Update transaction as successful
        transaction_manager.update_transaction_status(
            transaction_id,
            "SUCCESS",
            gateway_payment_id=mock_payment_id,
            gateway_signature=mock_signature,
            payment_captured=True,
            test_mode=True
        )
        
        # Update order status
        db = get_db()
        db.collection("orders").document(transaction["order_id"]).update({
            "orderStatus": "CONFIRMED",
            "paymentStatus": "PAID",
            "paymentVerifiedAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
            "gatewayPaymentId": mock_payment_id,
            "testMode": True
        })
        
        return jsonify({
            "success": True,
            "message": "Test payment simulated successfully",
            "payment_id": mock_payment_id,
            "redirect_to": url_for("order_success")
        })
        
    except Exception as e:
        print(f"❌ Test payment simulation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/test/fail_payment/<transaction_id>", methods=["POST"])
def test_fail_payment(transaction_id):
    """Test endpoint to simulate payment failure"""
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"success": False, "error": "Test mode not available"}), 403
    
    try:
        # Get transaction
        transaction = transaction_manager.get_transaction(transaction_id)
        if not transaction:
            return jsonify({"success": False, "error": "Transaction not found"}), 404
        
        # Update transaction as failed
        transaction_manager.update_transaction_status(
            transaction_id,
            "FAILED",
            error_message="Test payment failure",
            test_mode=True
        )
        
        return jsonify({
            "success": True,
            "message": "Test payment failure simulated",
            "status": "FAILED"
        })
        
    except Exception as e:
        print(f"❌ Test payment failure error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/test/payment_status")
def test_payment_status():
    """Test endpoint to check all payment statuses"""
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"success": False, "error": "Test mode not available"}), 403
    
    try:
        db = get_db()
        
        # Get recent transactions
        transactions = db.collection("transactions")\
                          .order_by("created_at", direction="DESCENDING")\
                          .limit(10)\
                          .get()
        
        transaction_list = []
        for doc in transactions:
            transaction_data = doc.to_dict()
            transaction_list.append({
                "transaction_id": transaction_data.get("transaction_id"),
                "order_id": transaction_data.get("order_id"),
                "status": transaction_data.get("status"),
                "amount": transaction_data.get("amount"),
                "created_at": transaction_data.get("created_at").isoformat() if transaction_data.get("created_at") else None,
                "test_mode": transaction_data.get("test_mode", False)
            })
        
        return jsonify({
            "success": True,
            "transactions": transaction_list
        })
        
    except Exception as e:
        print(f"❌ Test payment status error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

