import { NextResponse } from 'next/server';
import { translate } from '@vitalets/google-translate-api';

export async function POST(request: Request) {
    try {
        const { text, target } = await request.json();

        if (!text || !target) {
            return NextResponse.json(
                { error: 'Missing "text" or "target" language code in request body' },
                { status: 400 }
            );
        }

        // @ts-ignore - The library types might be slightly off in some versions or environments
        const res = await translate(text, { to: target });

        return NextResponse.json({
            original: text,
            translatedText: res.text,
            target: target
        });

    } catch (error: any) {
        console.error("Translation Error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to translate text" },
            { status: 500 }
        );
    }
}
