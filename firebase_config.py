import os
import firebase_admin
from firebase_admin import credentials, firestore, messaging

_db = None

# ---------------- FIREBASE INIT ----------------
def initialize_firebase():
    global _db

    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    # Check for Vercel environment variable first
    if os.getenv("VERCEL"):
        # Use environment variable for Vercel
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if service_account_json:
            try:
                import json
                cred = credentials.Certificate(json.loads(service_account_json))
                firebase_admin.initialize_app(cred)
                _db = firestore.client()
                print("✅ Firebase initialized (Vercel)")
                return _db
            except Exception as e:
                print(f"❌ Firebase init failed (Vercel): {e}")
                return None
        else:
            print("❌ FIREBASE_SERVICE_ACCOUNT not set")
            return None
    
    # Local development - use file
    cred_path = os.getenv("FIREBASE_CREDENTIALS")
    if not cred_path:
        print("⚠️ FIREBASE_CREDENTIALS not set")
        return None

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        print("✅ Firebase initialized (Local)")
        return _db
    except Exception as e:
        print(f"❌ Firebase init failed: {e}")
        return None


def get_db():
    global _db
    if _db is None:
        _db = initialize_firebase()
    return _db


# ---------------- MENU (DISABLED TEMPORARILY) ----------------
def get_menu():
    print("⚠️ get_menu disabled (safe mode)")
    return []


# ---------------- ORDERS ----------------
def save_order(order_data):
    try:
        db = get_db()

        # 🔥 Fallback if Firebase is unavailable
        if not db:
            print("⚠️ Firebase unavailable, using local order ID")
            return order_data.get("orderId")

        ref = db.collection("orders").document()
        order_data["createdAt"] = firestore.SERVER_TIMESTAMP
        ref.set(order_data)
        return ref.id

    except Exception as e:
        print(f"❌ create_order failed: {e}")
        return None


def get_all_orders():
    try:
        db = get_db()
        if not db:
            return []

        docs = (
            db.collection("orders")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(100)
            .get()
        )

        orders = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            orders.append(data)

        return orders

    except Exception as e:
        print(f"❌ get_all_orders failed: {e}")
        return []


def update_order_status(order_id, status):
    try:
        db = get_db()
        if not db:
            return False

        db.collection("orders").document(order_id).update({
            "orderStatus": status,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        return True

    except Exception as e:
        print(f"❌ update_order_status failed: {e}")
        return False


# ---------------- ADMIN TOKENS ----------------
def get_all_admin_tokens():
    try:
        db = get_db()
        if not db:
            return []

        docs = db.collection("admin_tokens").limit(100).get()
        return [d.id for d in docs]

    except Exception as e:
        print(f"❌ get_all_admin_tokens failed: {e}")
        return []


def send_push_to_admins(title, body):
    try:
        tokens = get_all_admin_tokens()
        if not tokens:
            print("⚠️ No admin tokens found")
            return False

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=tokens
        )

        messaging.send_multicast(message)
        return True

    except Exception as e:
        print(f"❌ Push failed: {e}")
        return False
