from flask import request, jsonify
from functools import wraps
import time
import hashlib
from datetime import datetime, timezone

class SecurityValidator:
    """Security validation utilities"""
    
    @staticmethod
    def validate_request_origin(f):
        """Validate request origin to prevent CSRF"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check Origin header for API requests
            if request.method == "POST" and request.is_json:
                origin = request.headers.get("Origin")
                referer = request.headers.get("Referer")
                
                # In production, validate against allowed domains
                allowed_origins = ["http://localhost:5000", "https://yourdomain.com"]
                
                if origin and origin not in allowed_origins:
                    return jsonify({
                        "success": False,
                        "error": "Invalid request origin"
                    }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    @staticmethod
    def generate_request_hash(data, secret_key):
        """Generate hash for request integrity"""
        if isinstance(data, dict):
            # Sort keys for consistent hashing
            sorted_data = {k: data[k] for k in sorted(data.keys())}
            data_string = str(sorted_data)
        else:
            data_string = str(data)
        
        return hashlib.sha256((data_string + secret_key).encode()).hexdigest()
    
    @staticmethod
    def validate_request_timestamp(timestamp, max_age_seconds=300):
        """Validate request timestamp to prevent replay attacks"""
        try:
            request_time = float(timestamp)
            current_time = time.time()
            age = current_time - request_time
            
            if age < 0 or age > max_age_seconds:
                return False, f"Request timestamp invalid. Age: {age}s"
            
            return True, "Timestamp valid"
        except (ValueError, TypeError):
            return False, "Invalid timestamp format"

class ErrorHandler:
    """Centralized error handling for payment flows"""
    
    @staticmethod
    def handle_payment_error(error_type, details=None, user_message=None):
        """Handle payment-related errors consistently"""
        error_responses = {
            "INVALID_SIGNATURE": {
                "success": False,
                "error": "Payment signature verification failed",
                "code": "SECURITY_ERROR",
                "user_message": "Security verification failed. Please try again."
            },
            "TRANSACTION_NOT_FOUND": {
                "success": False,
                "error": "Transaction not found",
                "code": "TRANSACTION_ERROR",
                "user_message": "Transaction not found. Please start a new order."
            },
            "PAYMENT_FAILED": {
                "success": False,
                "error": "Payment processing failed",
                "code": "PAYMENT_ERROR",
                "user_message": "Payment failed. Please try again or use another payment method."
            },
            "NETWORK_ERROR": {
                "success": False,
                "error": "Network connectivity issue",
                "code": "NETWORK_ERROR",
                "user_message": "Network issue. Please check your connection and try again."
            },
            "RATE_LIMIT_EXCEEDED": {
                "success": False,
                "error": "Too many payment attempts",
                "code": "RATE_LIMIT",
                "user_message": "Too many attempts. Please wait before trying again."
            },
            "SESSION_EXPIRED": {
                "success": False,
                "error": "Payment session expired",
                "code": "SESSION_ERROR",
                "user_message": "Payment session expired. Please start a new order."
            }
        }
        
        response = error_responses.get(error_type, {
            "success": False,
            "error": "Unknown payment error",
            "code": "UNKNOWN_ERROR",
            "user_message": "An error occurred. Please try again."
        })
        
        if details:
            response["details"] = details
        
        if user_message:
            response["user_message"] = user_message
        
        return response

class DuplicatePaymentPrevention:
    """Prevent duplicate payment submissions"""
    
    def __init__(self):
        self.recent_payments = {}  # In production, use Redis or database
    
    def is_duplicate_payment(self, order_id, payment_id, window_minutes=5):
        """Check if payment is a duplicate"""
        key = f"{order_id}_{payment_id}"
        current_time = time.time()
        window_seconds = window_minutes * 60
        
        # Check if payment was recently processed
        if key in self.recent_payments:
            last_attempt_time = self.recent_payments[key]
            if current_time - last_attempt_time < window_seconds:
                return True
        
        # Record this payment attempt
        self.recent_payments[key] = current_time
        
        # Clean old entries
        self._cleanup_old_payments(current_time, window_seconds)
        
        return False
    
    def _cleanup_old_payments(self, current_time, window_seconds):
        """Clean up old payment records"""
        keys_to_remove = []
        
        for key, timestamp in self.recent_payments.items():
            if current_time - timestamp > window_seconds:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.recent_payments[key]

class NetworkFailureHandler:
    """Handle network failures gracefully"""
    
    @staticmethod
    def with_retry(max_retries=3, backoff_factor=1.0):
        """Decorator for retrying network operations"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries):
                    try:
                        return f(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        # Don't retry on certain errors
                        if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                            break
                        
                        if attempt < max_retries - 1:
                            # Exponential backoff
                            sleep_time = backoff_factor * (2 ** attempt)
                            time.sleep(sleep_time)
                
                # All retries failed
                raise last_exception
            
            return decorated_function
        return decorator
    
    @staticmethod
    def handle_payment_gateway_failure(error, transaction_id):
        """Handle payment gateway failures"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Log the error
        print(f"Payment gateway failure for transaction {transaction_id}: {error_type}: {error_message}")
        
        # Determine appropriate response
        if "timeout" in error_message.lower():
            return ErrorHandler.handle_payment_error(
                "NETWORK_ERROR",
                details={"gateway_error": error_message},
                user_message="Payment gateway timeout. Please try again."
            )
        elif "connection" in error_message.lower():
            return ErrorHandler.handle_payment_error(
                "NETWORK_ERROR",
                details={"gateway_error": error_message},
                user_message="Unable to connect to payment gateway. Please try again."
            )
        elif "authentication" in error_message.lower():
            return ErrorHandler.handle_payment_error(
                "INVALID_SIGNATURE",
                details={"gateway_error": error_message},
                user_message="Payment gateway authentication failed."
            )
        else:
            return ErrorHandler.handle_payment_error(
                "PAYMENT_FAILED",
                details={"gateway_error": error_message},
                user_message="Payment processing failed. Please try again."
            )

# Global instances
security_validator = SecurityValidator()
error_handler = ErrorHandler()
duplicate_prevention = DuplicatePaymentPrevention()
network_handler = NetworkFailureHandler()
