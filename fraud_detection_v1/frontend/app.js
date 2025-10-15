document.getElementById('transaction-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    const amount = parseFloat(document.getElementById('amount').value);
    const merchant = document.getElementById('merchant').value;
    const location = document.getElementById('location').value;
    const resultDiv = document.getElementById('result');

    resultDiv.innerHTML = '<p>Analyzing...</p>';
    
    // In a real app, you would POST this data to your backend
    // For now, this is a placeholder to show the frontend is working.
    // We will connect this in Phase 4.
    
    // This is a placeholder for the logic that will eventually call the API
    setTimeout(() => {
        resultDiv.innerHTML = `
            <h2>Analysis Result (Placeholder)</h2>
            <p><strong>Amount:</strong> ${amount}</p>
            <p><strong>Merchant:</strong> ${merchant}</p>
            <p><strong>Status:</strong> Not yet connected to backend.</p>
        `;
    }, 1000);
});