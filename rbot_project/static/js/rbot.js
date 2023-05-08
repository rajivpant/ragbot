document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const responseDiv = document.getElementById('response');

    chatForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const prompt = document.getElementById('prompt').value;
        const decorator = document.getElementById('decorator').value;

        const data = new FormData();
        data.append('prompt', prompt);
        data.append('decorator', decorator);
        data.append('csrfmiddlewaretoken', document.getElementsByName('csrfmiddlewaretoken')[0].value);

        const requestOptions = {
            method: 'POST',
            body: data,
        };

        responseDiv.innerText = 'Generating response...';

        try {
            const response = await fetch('/rbot_app/chat/', requestOptions);
            if (response.ok) {
                const result = await response.json();
                responseDiv.innerText = result.reply;
            } else {
                responseDiv.innerText = 'Error: Unable to generate response.';
            }
        } catch (error) {
            responseDiv.innerText = 'Error: ' + error;
        }
    });
});
