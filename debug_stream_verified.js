const axios = require('axios');

async function debugStreamVarified() {
    try {
        console.log("Starting streaming test with buffering...");
        const response = await axios.post('https://text.pollinations.ai/v1/chat/completions', {
            messages: [{ role: 'user', content: 'Count to 5.' }],
            model: 'openai',
            stream: true
        }, {
            responseType: 'stream'
        });

        console.log("Connection established. Status:", response.status);

        let buffer = '';

        response.data.on('data', chunk => {
            buffer += chunk.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

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
                            process.stdout.write(content);
                        }
                    } catch (e) {
                        console.error("\nParse Error for line:", trimmed, e.message);
                    }
                }
            }
        });

        response.data.on('end', () => console.log("\nStream ended."));
        response.data.on('error', err => console.error("Stream error:", err));

    } catch (error) {
        console.error("Request Error:", error.message);
    }
}

debugStreamVarified();
