import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import util from 'util';

const execPromise = util.promisify(exec);

export async function POST(request: Request) {
    try {
        const { url } = await request.json();

        if (!url) {
            return NextResponse.json(
                { error: 'Missing "url" in request body' },
                { status: 400 }
            );
        }

        // Extract Video ID
        const videoIdMatch = url.match(/(?:v=|\/)([0-9A-Za-z_-]{11}).*/);
        const videoId = videoIdMatch ? videoIdMatch[1] : null;

        if (!videoId) {
            return NextResponse.json(
                { error: 'Invalid YouTube URL' },
                { status: 400 }
            );
        }

        // Run Python Script
        // NOTE: Requires 'pip install youtube-transcript-api' and python in PATH
        const scriptPath = path.join(process.cwd(), 'src', 'scripts', 'transcript.py');
        const command = `python "${scriptPath}" ${videoId}`;

        const { stdout, stderr } = await execPromise(command);

        if (stderr) {
            console.warn("Python Stderr:", stderr);
        }

        let result;
        try {
            result = JSON.parse(stdout.trim());
        } catch (e) {
            throw new Error("Failed to parse Python script output: " + stdout);
        }

        if (!result.success) {
            return NextResponse.json({ error: result.error }, { status: 400 });
        }

        return NextResponse.json({
            url,
            transcript: result.transcript,
            source: "youtube-transcript-api (Python)"
        });

    } catch (error: any) {
        console.error("YouTube Transcript Error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to fetch transcript." },
            { status: 500 }
        );
    }
}
