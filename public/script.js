document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('chat-toggle');
    const chatWidget = document.getElementById('chat-widget');
    const closeBtn = document.getElementById('chat-close');
    const userMessageInput = document.getElementById('userMessage');

    // Event listener for opening the chat widget
    toggleBtn.addEventListener('click', () => {
        chatWidget.classList.remove('hidden');
        toggleBtn.classList.add('hidden');
        
        // Show initial messages with a slight delay for a more natural feel
        setTimeout(() => {
            addMessage("Es werden keine personenbezogenen Daten gespeichert.", 'bot', 'bot-intro-message');
            setTimeout(() => {
                addMessage("Terminanfragen hier möglich.", 'bot', 'bot-intro-message');
                setTimeout(() => {
                    addMessage("Wie kann ich Ihnen behilflich sein?", 'bot');
                }, 500);
            }, 500);
        }, 300);
    });

    // Event listener for closing the chat widget
    closeBtn.addEventListener('click', () => {
        chatWidget.classList.add('hidden');
        toggleBtn.classList.remove('hidden');
    });

    // Event listener for sending a message on 'Enter' key press
    userMessageInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
});

// Function to add a message to the chat
function addMessage(text, sender, extraClass = '') {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message-bubble', `${sender}-message`);
    if (extraClass) {
        messageDiv.classList.add(extraClass);
    }
    messageDiv.innerHTML = text.replace(/\n/g, '<br>'); // Handle multiline messages
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight; // Auto-scroll to the bottom
}

// Function to send a message to the backend
async function sendMessage() {
    const userMessageInput = document.getElementById('userMessage');
    const typingIndicator = document.getElementById('typing-indicator');
    const userMessage = userMessageInput.value.trim();
    if (!userMessage) return;

    addMessage(userMessage, 'user');
    userMessageInput.value = '';
    
    typingIndicator.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userMessage })
        });

        const data = await response.json();
        
        setTimeout(() => {
            addMessage(data.reply, 'bot');
            typingIndicator.classList.add('hidden');
        }, 500);
    } catch (error) {
        console.error('Fehler beim Senden der Nachricht:', error);
        addMessage('Entschuldigung, ich kann gerade nicht antworten.', 'bot');
        typingIndicator.classList.add('hidden');
    }
}
