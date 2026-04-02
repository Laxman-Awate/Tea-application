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
    # For now, use SAMPLE_MENU directly to avoid Firebase issues
    print("🔥 Using SAMPLE_MENU (Firebase disabled)")
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
        # Try Firebase first
        db = get_db()
        if db:
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

            print(f"✅ Retrieved {len(orders)} orders from Firebase")
            return orders
        else:
            print("🔄 Firebase not available, using local orders")
            
    except Exception as e:
        print(f"❌ Firebase get_all_orders failed: {e}")
        print("🔄 Using local orders fallback")
    
    # Fallback to local files
    return get_all_orders_local_fallback()


def get_all_orders_local_fallback():
    """Read orders from local files when Firebase is not available"""
    try:
        import json
        import os
        from datetime import datetime
        
        orders = []
        local_orders_dir = "local_orders"
        
        if not os.path.exists(local_orders_dir):
            print("📁 No local orders directory found")
            return []
        
        # Read all JSON files in local_orders directory
        for filename in os.listdir(local_orders_dir):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(local_orders_dir, filename)
                    with open(filepath, 'r') as f:
                        order_data = json.load(f)
                        
                    # Ensure the order has proper structure
                    if 'orderId' in order_data or 'localOrderId' in order_data:
                        # Convert local timestamp back to datetime for consistency
                        if 'savedAt' in order_data:
                            try:
                                order_data['createdAt'] = datetime.fromisoformat(order_data['savedAt'])
                            except:
                                pass
                        
                        orders.append(order_data)
                        
                except Exception as e:
                    print(f"❌ Error reading {filename}: {e}")
        
        # Sort by creation time (newest first)
        orders.sort(key=lambda x: x.get('savedAt', ''), reverse=True)
        
        print(f"✅ Retrieved {len(orders)} orders from local files")
        return orders
        
    except Exception as e:
        print(f"❌ Local orders fallback failed: {e}")
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
