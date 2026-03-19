import hashlib
import hmac
import json
import time
import uuid
import requests
from datetime import datetime, timezone
from flask import current_app
import secrets

class PaymentGateway:
    """Secure Payment Gateway Integration (Razorpay-style)"""
    
    def __init__(self):
        self.api_key = "rzp_test_XXXXXXXXXXXXXXXX"  # Test key
        self.api_secret = "test_secret_XXXXXXXXXXXXXXXX"  # Test secret
        self.webhook_secret = "webhook_secret_XXXXXXXXXXXXXXXX"
        self.base_url = "https://api.razorpay.com/v1"
        
    def generate_order_id(self):
        """Generate secure order ID"""
        return f"order_{int(time.time())}_{secrets.token_hex(4)}"
    
    def create_order(self, amount, currency="INR", receipt=None):
        """Create payment order with secure parameters"""
        try:
            order_data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": currency,
                "receipt": receipt or self.generate_order_id(),
                "payment_capture": 1,
                "notes": {
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # In production, make actual API call
            # response = requests.post(f"{self.base_url}/orders", 
            #                        auth=(self.api_key, self.api_secret),
            #                        json=order_data)
            
            # For simulation, return mock response
            mock_order = {
                "id": self.generate_order_id(),
                "entity": "order",
                "amount": order_data["amount"],
                "currency": order_data["currency"],
                "receipt": order_data["receipt"],
                "status": "created",
                "created_at": int(time.time()),
                "notes": order_data["notes"]
            }
            
            return {
                "success": True,
                "order": mock_order,
                "razorpay_key": self.api_key
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_payment_signature(self, razorpay_order_id, razorpay_payment_id, 
                              razorpay_signature):
        """Verify payment signature to prevent tampering"""
        try:
            # Create signature string
            signature_string = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures securely
            return hmac.compare_digest(expected_signature, razorpay_signature)
            
        except Exception as e:
            current_app.logger.error(f"Signature verification error: {e}")
            return False
    
    def capture_payment(self, razorpay_payment_id, amount):
        """Capture payment after verification"""
        try:
            # In production, make actual API call
            # response = requests.post(f"{self.base_url}/payments/{razorpay_payment_id}/capture",
            #                        auth=(self.api_key, self.api_secret),
            #                        json={"amount": int(amount * 100)})
            
            # For simulation, return mock response
            mock_payment = {
                "id": razorpay_payment_id,
                "entity": "payment",
                "amount": int(amount * 100),
                "currency": "INR",
                "status": "captured",
                "captured": True,
                "created_at": int(time.time()),
                "order_id": None
            }
            
            return {
                "success": True,
                "payment": mock_payment
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_payment_status(self, payment_id):
        """Get payment status from gateway"""
        try:
            # In production, make actual API call
            # response = requests.get(f"{self.base_url}/payments/{payment_id}",
            #                        auth=(self.api_key, self.api_secret))
            
            # For simulation, check our database
            from firebase_config import get_db
            db = get_db()
            
            # Look up transaction by payment ID
            transactions = db.collection("transactions")\
                              .where("payment_id", "==", payment_id)\
                              .limit(1)\
                              .get()
            
            for doc in transactions:
                return {
                    "success": True,
                    "status": doc.to_dict().get("status", "unknown"),
                    "payment": doc.to_dict()
                }
            
            return {
                "success": False,
                "error": "Payment not found"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_webhook_signature(self, payload, signature):
        """Verify webhook signature for secure notifications"""
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            current_app.logger.error(f"Webhook signature verification error: {e}")
            return False

# Global payment gateway instance
payment_gateway = PaymentGateway()
