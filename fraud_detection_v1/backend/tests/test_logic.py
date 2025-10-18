# We need to import the function and the Pydantic model it uses
from app.main import analyze_transaction, TransactionCreate

# Testing legitimate transaction
def test_legitimate_transaction():
    """Tests that a normal transaction passes as legitimate."""
    tx_data = TransactionCreate(
        amount=100.00,
        merchant="Test Coffee Shop",
        location="New York"
    )
    is_fraud, reason = analyze_transaction(tx_data)
    
    assert is_fraud == False
    assert reason == "Legitimate"

# Testing a really high amount of transaction
def test_high_amount_fraud():
    """Tests the 'amount exceeds $1500' rule."""
    tx_data = TransactionCreate(
        amount=2000.00,
        merchant="Electronics Store",
        location="Miami"
    )
    is_fraud, reason = analyze_transaction(tx_data)
    
    assert is_fraud == True
    assert reason == "Amount exceeds $1500"

# Testing if the transaction is being done through unsafe channels
def test_high_risk_merchant_fraud():
    """Tests the 'high-risk merchant' rule."""
    tx_data = TransactionCreate(
        amount=50.00,
        merchant="a darkweb market", # Check lowercase matching
        location="Unknown"
    )
    is_fraud, reason = analyze_transaction(tx_data)
    
    assert is_fraud == True
    assert reason == "Transaction with high-risk merchant"

# Testing if the transaction is below the lowest amount 
def test_low_amount_fraud():
    """Tests the 'unusually low amount' rule."""
    tx_data = TransactionCreate(
        amount=0.50,
        merchant="Online Service",
        location="Global"
    )
    is_fraud, reason = analyze_transaction(tx_data)
    
    assert is_fraud == True
    assert reason == "Unusually low transaction amount"