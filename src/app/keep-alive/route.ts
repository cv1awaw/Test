import { NextResponse } from 'next/server';
import { CreateNewAxios } from '@/lib/utils';

// export const runtime = 'edge'; // Removed to ensure it runs in the same Node.js environment as the chat API
export const dynamic = 'force-dynamic'; // Prevent Vercel from caching this route, ensuring it always hits the server

export async function GET() {
    try {
        // "Deep Warm-up": Ping the external API to keep the TLS session/TCP connection active in the pool
        // We use a short timeout because we don't want this to hang for long if the provider is down
        const client = CreateNewAxios({ baseURL: 'https://text.pollinations.ai' });

        // Concurrent Pool Inflation: Fire multiple requests at once to force opening multiple sockets
        const warmUpCount = 2; // Scaled down from 5 to 2 to reduce resource usage
        const warmUpRequests = Array.from({ length: warmUpCount }).map(() =>
            client.get('/', { timeout: 3000 }).catch(e => {
                // Ignore individual failures, we just want to try opening sockets
                return null;
            })
        );

        // Wait for all to finish (success or fail) so sockets are returned to pool
        await Promise.all(warmUpRequests);

        return NextResponse.json({
            status: 'alive',
            mode: 'deep-warmup',
            timestamp: new Date().toISOString(),
        });
    } catch (e) {
        // Even if deep warm-up fails, the server is "alive"
        return NextResponse.json({
            status: 'alive',
            mode: 'basic',
            timestamp: new Date().toISOString(),
        });
    }
}
