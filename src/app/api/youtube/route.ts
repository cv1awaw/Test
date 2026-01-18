import { NextResponse } from 'next/server';
import { YoutubeTranscript } from 'youtube-transcript';

export async function POST(request: Request) {
    try {
        const { url } = await request.json();

        if (!url) {
            return NextResponse.json(
                { error: 'Missing "url" in request body' },
                { status: 400 }
            );
        }

        // Fetch transcript
        // Note: This library might fail on some Vercel edge networks due to IP blocking, 
        // but should work locally or on robust servers.
        const transcriptItems = await YoutubeTranscript.fetchTranscript(url);

        const fullText = transcriptItems.map(item => item.text).join(' ');

        return NextResponse.json({
            url,
            transcript: fullText,
            items: transcriptItems
        });

    } catch (error: any) {
        console.error("YouTube Transcript Error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to fetch transcript. Video might not have captions or is restricted." },
            { status: 500 }
        );
    }
}
