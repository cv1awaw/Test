const axios = require('axios');

async function debugStream() {
    try {
        console.log("Starting streaming test...");
        const response = await axios.post('https://text.pollinations.ai/v1/chat/completions', {
            messages: [{ role: 'user', content: 'Tell me a short joke.' }],
            model: 'openai',
            stream: true
        }, {
            responseType: 'stream'
        });

        console.log("Connection established. Status:", response.status);

        response.data.on('data', chunk => {
            const chunkStr = chunk.toString();
            console.log("RAW CHUNK:", JSON.stringify(chunkStr));

            const lines = chunkStr.split('\n');
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;
                if (trimmed === 'data: [DONE]') {
                    console.log("Found [DONE]");
                    return;
                }

                if (trimmed.startsWith('data: ')) {
                    try {
                        const jsonStr = trimmed.substring(6);
                        const json = JSON.parse(jsonStr);
                        const content = json.choices?.[0]?.delta?.content;
                        if (content) {
                            console.log("Parsed Content:", content);
                        }
                    } catch (e) {
                        console.error("Parse Error for line:", trimmed, e.message);
                    }
                } else {
                    console.log("Ignored line:", trimmed);
                }
            }
        });

        response.data.on('end', () => console.log("Stream ended."));
        response.data.on('error', err => console.error("Stream error:", err));

    } catch (error) {
        console.error("Request Error:", error.message);
        if (error.response) {
            console.error("Response Status:", error.response.status);
            error.response.data.pipe(process.stdout);
        }
    }
}

debugStream();
