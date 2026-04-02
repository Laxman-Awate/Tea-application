import os
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import timezone

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


# ---------------- MENU ----------------
def get_menu():
    try:
        print("🔥 Attempting to get menu from Firebase...")
        db = get_db()
        
        if not db:
            print("❌ Firebase DB not available for menu")
            return []

        # Get menu items from Firestore
        docs = db.collection("menu").get()
        menu_items = []
        
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            menu_items.append(item)
        
        print(f"✅ Retrieved {len(menu_items)} menu items from Firebase")
        return menu_items

    except Exception as e:
        print(f"❌ get_menu failed: {e}")
        return []


# ---------------- ORDERS ----------------
def save_order(order_data):
    try:
        print("🔥 Attempting to save order to Firebase...")
        db = get_db()
        
        if not db:
            print("❌ Firebase DB not available - using local fallback")
            print("🔍 Environment variables:", {
                "VERCEL": os.getenv("VERCEL"),
                "FIREBASE_SERVICE_ACCOUNT": "SET" if os.getenv("FIREBASE_SERVICE_ACCOUNT") else "NOT SET",
                "FIREBASE_CREDENTIALS": os.getenv("FIREBASE_CREDENTIALS")
            })
            
            # Fallback: Save to local file for development
            return save_order_local_fallback(order_data)

        print("✅ Firebase DB available, saving order...")
        ref = db.collection("orders").document()
        order_data["createdAt"] = firestore.SERVER_TIMESTAMP
        ref.set(order_data)
        print(f"✅ Order saved with ID: {ref.id}")
        return ref.id

    except Exception as e:
        print(f"❌ save_order failed: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        
        # Fallback to local storage
        print("🔄 Using local fallback storage")
        return save_order_local_fallback(order_data)


def save_order_local_fallback(order_data):
    """Fallback to save orders locally when Firebase is not available"""
    try:
        import json
        from datetime import datetime
        
        # Create local orders directory if it doesn't exist
        os.makedirs("local_orders", exist_ok=True)
        
        # Generate local order ID
        import uuid
        local_order_id = f"local_{uuid.uuid4().hex[:8]}"
        
        # Add local metadata
        order_data["localOrderId"] = local_order_id
        order_data["savedLocally"] = True
        order_data["savedAt"] = datetime.now(timezone.utc).isoformat()
        
        # Save to local file
        filename = f"local_orders/order_{local_order_id}.json"
        with open(filename, 'w') as f:
            json.dump(order_data, f, indent=2, default=str)
        
        print(f"✅ Order saved locally: {filename}")
        return local_order_id
        
    except Exception as e:
        print(f"❌ Local fallback also failed: {e}")
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
