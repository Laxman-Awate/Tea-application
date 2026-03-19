from functools import wraps
from flask import request, jsonify, redirect, session, current_app
from transaction_manager import TransactionManager
import time

def require_payment_verified(f):
    """Middleware to require payment verification before accessing protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user has verified payment session
        verified_payment = session.get('verified_payment')
        
        if not verified_payment:
            return jsonify({
                "success": False,
                "error": "Payment verification required",
                "redirect_to": "/payment"
            }), 403
        
        # Verify transaction status
        transaction_id = verified_payment.get('transaction_id')
        security_token = verified_payment.get('security_token')
        
        if not transaction_id or not security_token:
            session.pop('verified_payment', None)
            return jsonify({
                "success": False,
                "error": "Invalid payment session",
                "redirect_to": "/payment"
            }), 403
        
        # Verify transaction access
        verification = TransactionManager.verify_transaction_access(
            transaction_id, security_token, request
        )
        
        if not verification["valid"]:
            session.pop('verified_payment', None)
            return jsonify({
                "success": False,
                "error": verification["error"],
                "redirect_to": "/payment"
            }), 403
        
        transaction = verification["transaction"]
        
        # Check if payment is successful
        if transaction.get("status") != "SUCCESS":
            session.pop('verified_payment', None)
            return jsonify({
                "success": False,
                "error": "Payment not successful",
                "payment_status": transaction.get("status"),
                "redirect_to": "/payment"
            }), 403
        
        # Add transaction to request context
        request.current_transaction = transaction
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_payment_session(f):
    """Validate payment session before accessing payment-related routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if there's a pending payment in session
        pending_payment = session.get('pending_payment')
        
        if not pending_payment:
            return redirect('/')
        
        # Validate pending payment data
        required_fields = ['order_id', 'order_code', 'total']
        for field in required_fields:
            if field not in pending_payment:
                session.pop('pending_payment', None)
                return redirect('/')
        
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit_payment_attempts(max_attempts=5, window_minutes=15):
    """Rate limiting for payment attempts to prevent abuse"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr
            
            # Check rate limit using session or database
            rate_limit_key = f"payment_rate_limit_{client_ip}"
            current_time = time.time()
            window_start = current_time - (window_minutes * 60)
            
            # Check existing attempts in session
            attempts = session.get(rate_limit_key, [])
            
            # Filter attempts within window
            recent_attempts = [attempt for attempt in attempts if attempt > window_start]
            
            if len(recent_attempts) >= max_attempts:
                return jsonify({
                    "success": False,
                    "error": "Too many payment attempts. Please try again later.",
                    "retry_after": window_minutes * 60
                }), 429
            
            # Add current attempt
            recent_attempts.append(current_time)
            session[rate_limit_key] = recent_attempts
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def validate_payment_payload(f):
    """Validate payment payload for security"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            # Check content type
            if not request.is_json:
                return jsonify({
                    "success": False,
                    "error": "Invalid content type"
                }), 400
            
            # Get payment data
            payment_data = request.get_json()
            
            if not payment_data:
                return jsonify({
                    "success": False,
                    "error": "No payment data provided"
                }), 400
            
            # Validate required fields
            required_fields = ['order_id', 'payment_id', 'signature']
            for field in required_fields:
                if field not in payment_data:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required field: {field}"
                    }), 400
            
            # Validate field formats
            if not isinstance(payment_data['order_id'], str) or len(payment_data['order_id']) < 5:
                return jsonify({
                    "success": False,
                    "error": "Invalid order ID format"
                }), 400
            
            if not isinstance(payment_data['payment_id'], str) or len(payment_data['payment_id']) < 5:
                return jsonify({
                    "success": False,
                    "error": "Invalid payment ID format"
                }), 400
            
            if not isinstance(payment_data['signature'], str) or len(payment_data['signature']) < 10:
                return jsonify({
                    "success": False,
                    "error": "Invalid signature format"
                }), 400
            
            # Add validated data to request
            request.validated_payment_data = payment_data
        
        return f(*args, **kwargs)
    
    return decorated_function

def secure_transaction_access(f):
    """Ensure secure access to transaction endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        transaction_id = kwargs.get('transaction_id') or request.json.get('transaction_id')
        
        if not transaction_id:
            return jsonify({
                "success": False,
                "error": "Transaction ID required"
            }), 400
        
        # Get security token from header or request
        security_token = request.headers.get('X-Security-Token') or request.json.get('security_token')
        
        if not security_token:
            return jsonify({
                "success": False,
                "error": "Security token required"
            }), 401
        
        # Verify transaction access
        verification = TransactionManager.verify_transaction_access(
            transaction_id, security_token, request
        )
        
        if not verification["valid"]:
            return jsonify({
                "success": False,
                "error": verification["error"]
            }), 403
        
        # Add transaction to request context
        request.current_transaction = verification["transaction"]
        
        return f(*args, **kwargs)
    
    return decorated_function

def log_payment_activity(activity_type):
    """Decorator to log payment activities for security auditing"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                success = True
                status_code = getattr(result, 'status_code', 200)
            except Exception as e:
                result = None
                success = False
                status_code = 500
                current_app.logger.error(f"Payment activity error: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Log activity
            log_data = {
                "activity_type": activity_type,
                "success": success,
                "status_code": status_code,
                "duration": duration,
                "ip_address": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
                "timestamp": datetime.now().isoformat(),
                "endpoint": request.endpoint,
                "method": request.method
            }
            
            # Add transaction ID if available
            if hasattr(request, 'current_transaction'):
                log_data["transaction_id"] = request.current_transaction.get("transaction_id")
            
            # Store in audit log (in production, use proper logging service)
            current_app.logger.info(f"Payment Activity: {json.dumps(log_data)}")
            
            return result
        
        return decorated_function
    return decorator
