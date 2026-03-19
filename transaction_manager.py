from datetime import datetime, timezone, timedelta
from firebase_config import get_db
import uuid
import secrets

class TransactionManager:
    """Secure Transaction Management System"""
    
    @staticmethod
    def create_transaction(order_id, amount, customer_name, customer_email=None):
        """Create secure transaction record"""
        db = get_db()
        
        transaction_id = f"txn_{secrets.token_hex(8)}"
        transaction_data = {
            "transaction_id": transaction_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "customer_name": customer_name,
            "customer_email": customer_email,
            "status": "INITIATED",
            "payment_method": "UPI",
            "gateway_order_id": None,
            "gateway_payment_id": None,
            "gateway_signature": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),  # 15 min expiry
            "retry_count": 0,
            "max_retries": 3,
            "security_token": secrets.token_urlsafe(32),
            "ip_address": None,  # Will be set from request
            "user_agent": None   # Will be set from request
        }
        
        # Store transaction
        db.collection("transactions").document(transaction_id).set(transaction_data)
        
        return transaction_data
    
    @staticmethod
    def update_transaction_status(transaction_id, status, **kwargs):
        """Update transaction status with security checks"""
        db = get_db()
        
        transaction_ref = db.collection("transactions").document(transaction_id)
        transaction_doc = transaction_ref.get()
        
        if not transaction_doc.exists:
            raise Exception("Transaction not found")
        
        transaction_data = transaction_doc.to_dict()
        
        # Security check: Don't allow status downgrade
        status_hierarchy = {
            "INITIATED": 0,
            "PROCESSING": 1,
            "SUCCESS": 2,
            "FAILED": 3,
            "CANCELLED": 4,
            "EXPIRED": 5
        }
        
        current_level = status_hierarchy.get(transaction_data.get("status", "INITIATED"), 0)
        new_level = status_hierarchy.get(status, 0)
        
        # Allow certain transitions
        allowed_transitions = {
            "INITIATED": ["PROCESSING", "CANCELLED", "EXPIRED"],
            "PROCESSING": ["SUCCESS", "FAILED", "CANCELLED"],
            "SUCCESS": [],  # Final state
            "FAILED": ["PROCESSING"],  # Allow retry
            "CANCELLED": [],  # Final state
            "EXPIRED": ["INITIATED"]  # Allow re-initiation
        }
        
        if status not in allowed_transitions.get(transaction_data.get("status"), []):
            raise Exception(f"Invalid status transition from {transaction_data.get('status')} to {status}")
        
        # Update transaction
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
            **kwargs
        }
        
        transaction_ref.update(update_data)
        
        # Return updated transaction
        updated_doc = transaction_ref.get()
        return updated_doc.to_dict()
    
    @staticmethod
    def get_transaction(transaction_id):
        """Get transaction with security validation"""
        db = get_db()
        
        transaction_doc = db.collection("transactions").document(transaction_id).get()
        
        if not transaction_doc.exists:
            return None
        
        transaction_data = transaction_doc.to_dict()
        
        # Security check: Check if transaction is expired
        if transaction_data.get("expires_at"):
            if datetime.now(timezone.utc) > transaction_data["expires_at"]:
                if transaction_data.get("status") in ["INITIATED", "PROCESSING"]:
                    # Auto-expire transaction
                    TransactionManager.update_transaction_status(
                        transaction_id, "EXPIRED"
                    )
                    transaction_data["status"] = "EXPIRED"
        
        return transaction_data
    
    @staticmethod
    def verify_transaction_access(transaction_id, security_token, request):
        """Verify transaction access with security token"""
        transaction = TransactionManager.get_transaction(transaction_id)
        
        if not transaction:
            return {"valid": False, "error": "Transaction not found"}
        
        # Verify security token
        if transaction.get("security_token") != security_token:
            return {"valid": False, "error": "Invalid security token"}
        
        # Check IP address (optional security measure)
        if transaction.get("ip_address") and request.remote_addr:
            if transaction["ip_address"] != request.remote_addr:
                return {"valid": False, "error": "IP address mismatch"}
        
        return {"valid": True, "transaction": transaction}
    
    @staticmethod
    def record_payment_attempt(transaction_id, payment_data, request):
        """Record payment attempt with security context"""
        db = get_db()
        
        attempt_data = {
            "attempt_id": f"att_{secrets.token_hex(8)}",
            "transaction_id": transaction_id,
            "gateway_order_id": payment_data.get("order_id"),
            "gateway_payment_id": payment_data.get("payment_id"),
            "gateway_signature": payment_data.get("signature"),
            "amount": payment_data.get("amount"),
            "status": "ATTEMPTED",
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get("User-Agent"),
            "created_at": datetime.now(timezone.utc)
        }
        
        # Store attempt
        db.collection("payment_attempts").document(attempt_data["attempt_id"]).set(attempt_data)
        
        # Update transaction retry count
        transaction = TransactionManager.get_transaction(transaction_id)
        if transaction:
            retry_count = transaction.get("retry_count", 0) + 1
            db.collection("transactions").document(transaction_id).update({
                "retry_count": retry_count,
                "ip_address": request.remote_addr,
                "user_agent": request.headers.get("User-Agent")
            })
        
        return attempt_data
    
    @staticmethod
    def get_transaction_by_order_id(order_id):
        """Get transaction by order ID"""
        db = get_db()
        
        transactions = db.collection("transactions")\
                          .where("order_id", "==", order_id)\
                          .order_by("created_at", direction="DESCENDING")\
                          .limit(1)\
                          .get()
        
        for doc in transactions:
            return doc.to_dict()
        
        return None
    
    @staticmethod
    def cleanup_expired_transactions():
        """Clean up expired transactions (background task)"""
        db = get_db()
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        expired_transactions = db.collection("transactions")\
                                 .where("created_at", "<", cutoff_time)\
                                 .where("status", "in", ["INITIATED", "PROCESSING", "FAILED"])\
                                 .get()
        
        for doc in expired_transactions:
            doc.reference.update({"status": "EXPIRED"})
        
        return len(expired_transactions)

# Global transaction manager instance
transaction_manager = TransactionManager()
