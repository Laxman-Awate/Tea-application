# ------------------ TEST MODE ------------------
@app.route("/test/simulate_payment/<transaction_id>", methods=["POST"])
def test_simulate_payment(transaction_id):
    """Test endpoint to simulate successful payment"""
    if not os.environ.get("FLASK_ENV") == "development":
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
    if not os.environ.get("FLASK_ENV") == "development":
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
    if not os.environ.get("FLASK_ENV") == "development":
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
