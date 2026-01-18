import { NextResponse } from "next/server";
import { statsManager } from "@/lib/stats";
import { getConnectionStats } from "@/lib/utils";

export const dynamic = 'force-dynamic'; // Ensure this is not cached by Next.js

export async function GET() {
    const appStats = await statsManager.getStats();
    const connectionStats = getConnectionStats();
    const dbUsage = await statsManager.getDbUsage();

    return NextResponse.json({
        ...appStats,
        connectionStats,
        dbUsage
    });
}

export async function DELETE() {
    try {
        await statsManager.flushAll();
        return NextResponse.json({ success: true, message: "Database flushed" });
    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
