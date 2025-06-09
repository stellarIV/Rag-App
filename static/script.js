document.addEventListener('DOMContentLoaded', function() {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    // const uploadFile = document.getElementById('uploadFile'); // Removed
    // const uploadBtn = document.getElementById('uploadBtn');   // Removed
    const clearDbBtn = document.getElementById('clearDbBtn');

    function appendMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
        messageDiv.textContent = message;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        appendMessage('user', message);
        userInput.value = '';

        const typingIndicator = document.createElement('div');
        typingIndicator.classList.add('message', 'bot-message', 'typing-indicator');
        typingIndicator.textContent = 'ቦት እያሰበ ነው... እባክዎ ይጠብቁ...';
        chatMessages.appendChild(typingIndicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message }),
            });

            const data = await response.json();
            
            chatMessages.removeChild(typingIndicator);

            if (response.ok) {
                appendMessage('bot', data.response);
            } else {
                appendMessage('bot', data.response || 'ችግር ተፈጥሯል።');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            chatMessages.removeChild(typingIndicator);
            appendMessage('bot', 'የአውታረ መረብ ስህተት ተከስቷል። እባክዎ እንደገና ይሞክሩ።');
        }
    }

    // Removed the async function uploadDocument() { ... }

    async function clearDatabase() {
        if (!confirm('መረጃ ቋቱን ሙሉ በሙሉ ማጽዳት ይፈልጋሉ? ይህ ሁሉንም የተከማቸ መረጃ ይሰርዛል።')) {
            return;
        }

        appendMessage('bot', 'መረጃ ቋት እየጸዳ ነው። እባክዎ ይጠብቁ...');

        try {
            const response = await fetch('/clear_db', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (response.ok) {
                appendMessage('bot', `መረጃ ቋት ጸድቷል: ${data.message}`);
                alert('መረጃ ቋት በተሳካ ሁኔታ ጸድቷል። እባክዎ ለውጦቹን ለማንቃት አፕሊኬሽኑን እንደገና ያስጀምሩ።');
            } else {
                appendMessage('bot', `መረጃ ቋት ማጽዳት አልተሳካም: ${data.message || 'ያልታወቀ ስህተት'}`);
            }
        } catch (error) {
            console.error('Error clearing database:', error);
            appendMessage('bot', 'መረጃ ቋት ለማጽዳት የአውታረ መረብ ስህተት ተከስቷል።');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
    // Removed: uploadBtn.addEventListener('click', uploadDocument);
    clearDbBtn.addEventListener('click', clearDatabase);
});