const axios = require('axios');

async function verifyFix() {
    try {
        console.log("Verifying /v1/chat/completions endpoint...");
        const response = await axios.post('https://text.pollinations.ai/v1/chat/completions', {
            messages: [{ role: 'user', content: 'Hello' }],
            model: 'openai',
            stream: false
        });

        console.log("Status:", response.status);
        if (response.status === 200) {
            console.log("Response Data Snippet:", JSON.stringify(response.data).substring(0, 200));
            console.log("SUCCESS: Endpoint works.");
        } else {
            console.log("FAILED: Status code " + response.status);
        }

    } catch (error) {
        console.error("Error:", error.message);
    }
}

verifyFix();
