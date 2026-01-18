const axios = require('axios');

async function testApi() {
    console.log('Testing /api/chat endpoint...');

    const payload = {
        model: 'gpt-3.5-turbo',
        messages: [
            { role: 'user', content: 'Hello, are you working?' }
        ],
        stream: false
    };

    // Ensure you are targeting the running server port, typically 3000
    const url = 'http://localhost:3000/api/chat';

    try {
        const response = await axios.post(url, payload);
        console.log('✅ API Success!');
        console.log('Response Status:', response.status);
        console.log('Response Data:', JSON.stringify(response.data, null, 2));
    } catch (error) {
        console.error('❌ API Failed');
        if (error.response) {
            console.error('Status:', error.response.status);
            console.error('Data:', error.response.data);
        } else {
            console.error('Error:', error.message);
        }
    }
}

testApi();
