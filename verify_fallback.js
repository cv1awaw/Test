import { Pollinations } from './src/lib/model/pollination/index';
import { EventStream, Event } from './src/lib/utils/index';

async function testFallback() {
    console.log("Starting Fallback Verification...");

    const pollination = new Pollinations();
    const stream = new EventStream();

    stream.stream().on('data', (chunk) => {
        const str = chunk.toString();
        if (str.includes('event: message')) {
            process.stdout.write(JSON.parse(str.replace('event: message\ndata: ', '').trim()).content);
        }
    });

    console.log("Testing with INVALID model to force fallback...");
    // We pass a non-existent model to force the API to fail (or at least we hope it fails so we trigger fallback)
    // However, if Pollinations auto-defaults invalid models to OpenAI, this might just work immediately without fallback.
    // But let's verify if the code runs without crashing.
    try {
        await pollination.askStream({
            messages: [{ role: 'user', content: 'Hi, are you working?' }],
            model: 'invalid-model-name-xyz',
            prompt: 'Hi'
        }, stream);
        console.log("\nStream finished.");
    } catch (e) {
        console.error("Stream failed:", e);
    }
}

testFallback();
