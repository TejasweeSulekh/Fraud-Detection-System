document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('transaction-form');
    const formMessage = document.getElementById('form-message');
    const resultsContainer = document.getElementById('results');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    const API_URL = 'http://localhost:8000';
    const WS_URL = 'ws://localhost:8000/ws';

    // --- WebSocket Connection ---
    let socket;

    function connectWebSocket() {
        socket = new WebSocket(WS_URL);

        socket.onopen = () => {
            console.log('WebSocket connected');
            statusDot.classList.remove('status-disconnected');
            statusDot.classList.add('status-connected');
            statusText.textContent = 'Connected';
        };

        socket.onmessage = (event) => {
            const result = JSON.parse(event.data);
            console.log('Received result:', result);
            displayResult(result);
        };

        socket.onclose = () => {
            console.log('WebSocket disconnected. Reconnecting in 3 seconds...');
            statusDot.classList.remove('status-connected');
            statusDot.classList.add('status-disconnected');
            statusText.textContent = 'Disconnected. Retrying...';
            setTimeout(connectWebSocket, 3000);
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            socket.close();
        };
    }

    // --- Display Logic ---
    function displayResult(result) {
        // Clear the initial "Waiting..." message
        const waitingMessage = resultsContainer.querySelector('p');
        if (waitingMessage) {
            waitingMessage.remove();
        }

        const decisionClass = result.is_fraud ? 'blocked' : 'approved';
        const decisionText = result.is_fraud ? 'BLOCKED (Fraud)' : 'Approved';
        const tx = result.transaction;

        const resultElement = document.createElement('div');
        resultElement.className = 'p-4 border rounded-lg bg-gray-50';
        
        resultElement.innerHTML = `
            <div class="flex justify-between items-start">
                <div>
                    <p class="font-semibold text-gray-800">User: ${tx.user_id}</p>
                    <p class="text-sm text-gray-600">Merchant: ${tx.merchant_id}</p>
                </div>
                <div class="text-right">
                    <p class="text-lg font-bold text-gray-900">$${Number(tx.amount).toFixed(2)}</p>
                    <p class="text-sm font-bold ${decisionClass}">${decisionText}</p>
                </div>
            </div>
            <div class="mt-2 text-xs text-gray-500">
                <span>Fraud Score: ${result.fraud_score}</span> | <span>Timestamp: ${new Date(tx.timestamp).toLocaleTimeString()}</span>
            </div>
        `;
        
        resultsContainer.prepend(resultElement);
        // Add a class to trigger animation then remove it
        // setTimeout(() => resultElement.classList.remove('animate-pulse-fast'), 500);
    }
    
    // --- Form Submission ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const transactionData = {
            user_id: formData.get('user_id'),
            amount: parseFloat(formData.get('amount')),
            merchant_id: formData.get('merchant_id'),
            timestamp: new Date().toISOString() 
        };

        try {
            const response = await fetch(`${API_URL}/transaction`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(transactionData)
            });

            if (response.ok) {
                formMessage.textContent = 'Transaction submitted successfully!';
                formMessage.className = 'mt-4 text-center text-sm text-green-600';
                form.reset();
            } else {
                throw new Error('Failed to submit transaction.');
            }
        } catch (error) {
            formMessage.textContent = error.message;
            formMessage.className = 'mt-4 text-center text-sm text-red-600';
        }
        
        setTimeout(() => formMessage.textContent = '', 3000);
    });
    
    // --- Initial Kick-off ---
    connectWebSocket();
});
