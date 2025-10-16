// Define the base URL of your API.
const API_URL = 'http://localhost:8000';

const transactionForm = document.getElementById('transaction-form');
const resultDiv = document.getElementById('result');
const transactionListDiv = document.getElementById('transaction-list');

// --- Function to fetch and display all transactions ---
async function fetchTransactions() {
    try {
        const response = await fetch(`${API_URL}/transactions`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const transactions = await response.json();

        // Clear the loading message
        transactionListDiv.innerHTML = '';

        if (transactions.length === 0) {
            transactionListDiv.innerHTML = '<p>No transactions found.</p>';
            return;
        }

        // Create a table to display the transactions
        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Amount</th>
                    <th>Merchant</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${transactions.map(t => `
                    <tr class="${t.is_fraud ? 'fraud' : ''}">
                        <td>${t.id}</td>
                        <td>$${t.amount.toFixed(2)}</td>
                        <td>${t.merchant}</td>
                        <td>${t.is_fraud ? `Fraud (${t.fraud_reason})` : 'Legitimate'}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        transactionListDiv.appendChild(table);

    } catch (error) {
        transactionListDiv.innerHTML = `<p style="color: red;">Error fetching transactions: ${error.message}</p>`;
        console.error('Error fetching transactions:', error);
    }
}


// --- Function to handle form submission ---
transactionForm.addEventListener('submit', async function(event) {
    event.preventDefault();

    const amount = parseFloat(document.getElementById('amount').value);
    const merchant = document.getElementById('merchant').value;
    const location = document.getElementById('location').value;

    resultDiv.innerHTML = '<p>Analyzing...</p>';
    
    try {
        const response = await fetch(`${API_URL}/transaction`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                amount: amount,
                merchant: merchant,
                location: location
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        // Display the result of the new transaction
        let statusText = result.is_fraud 
            ? `Fraud Detected: ${result.fraud_reason}`
            : "Transaction is Legitimate";
        
        resultDiv.innerHTML = `
            <h2>Analysis Result</h2>
            <p><strong>Transaction ID:</strong> ${result.id}</p>
            <p><strong>Status:</strong> <span class="${result.is_fraud ? 'fraud-text' : ''}">${statusText}</span></p>
        `;

        // After submitting, refresh the transaction list to include the new one
        fetchTransactions();

    } catch (error) {
        resultDiv.innerHTML = `<p style="color: red;">Error submitting transaction: ${error.message}</p>`;
        console.error('Error submitting transaction:', error);
    }
});


// --- Initial Load ---
// When the page first loads, fetch and display the transaction history.
document.addEventListener('DOMContentLoaded', () => {
    fetchTransactions();
});