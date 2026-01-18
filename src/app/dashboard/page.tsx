'use client';

import { useEffect, useState } from "react";

interface RequestLog {
    id: string;
    timestamp: number;
    model: string;
    status: number;
    duration: number;
    cached: boolean;
    preview: string;
}

interface ConnectionStats {
    activeConnections: number;
    idleConnections: number;
    waitingRequests: number;
    maxFreeSockets: number;
}

interface DashboardStats {
    dailyRequests: number;
    monthlyRequests: number;
    totalRequests: number;
    requestsByModel: Record<string, number>;
    logs: RequestLog[];
    connectionStats?: ConnectionStats;
    dbUsage: { keys: number };
}

export default function DashboardPage() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [purging, setPurging] = useState(false);

    const fetchStats = async () => {
        try {
            const res = await fetch('/api/stats');
            if (res.ok) {
                const data = await res.json();
                setStats(data);
            }
        } catch (error) {
            console.error("Failed to fetch stats", error);
        } finally {
            setLoading(false);
        }
    };

    const handlePurge = async () => {
        if (!confirm("Are you sure you want to DELETE ALL DATA? This cannot be undone.")) return;
        setPurging(true);
        try {
            await fetch('/api/stats', { method: 'DELETE' });
            await fetchStats(); // Refresh
        } catch (e) {
            alert("Failed to purge");
        } finally {
            setPurging(false);
        }
    };

    useEffect(() => {
        fetchStats();
        const interval = setInterval(fetchStats, 2000); // Poll every 2 seconds
        return () => clearInterval(interval);
    }, []);

    if (loading && !stats) {
        return <div className="min-h-screen flex items-center justify-center text-white">Loading Dashboard...</div>;
    }

    const { dailyRequests, monthlyRequests, totalRequests, logs, connectionStats, dbUsage } = stats || {
        dailyRequests: 0,
        monthlyRequests: 0,
        totalRequests: 0,
        requestsByModel: {},
        logs: [],
        connectionStats: { activeConnections: 0, idleConnections: 0, waitingRequests: 0, maxFreeSockets: 0 },
        dbUsage: { keys: 0 }
    };

    const hotSockets = connectionStats?.idleConnections || 0;
    const maxHot = connectionStats?.maxFreeSockets || 5;

    return (
        <main className="min-h-screen p-6 md:p-12 relative bg-[#0a0a0a] text-white font-sans">
            {/* Header */}
            <header className="flex justify-between items-center mb-12">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                        API Command Center
                    </h1>
                    <p className="text-gray-400 mt-1">Real-time Monitoring & Analytics</p>
                </div>
                <div className="flex items-center gap-4">
                    <button
                        onClick={handlePurge}
                        disabled={purging}
                        className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        {purging ? "Purging..." : "Purge Database"}
                    </button>
                    <div className="flex items-center gap-3 bg-white/5 px-4 py-2 rounded-full border border-white/10">
                        <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                        <span className="text-sm font-medium text-green-400">System Online</span>
                    </div>
                </div>
            </header>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
                {/* Daily Usage */}
                <div className="glass-panel p-6 rounded-2xl bg-white/5 border border-white/10 relative overflow-hidden">
                    <h3 className="text-gray-400 font-medium text-sm">Daily Requests</h3>
                    <p className="text-4xl font-bold text-white mt-2">{dailyRequests}</p>
                    <div className="mt-4 text-xs text-blue-400 font-medium">Reset at midnight</div>
                </div>

                {/* Monthly Usage */}
                <div className="glass-panel p-6 rounded-2xl bg-white/5 border border-white/10 relative overflow-hidden">
                    <h3 className="text-gray-400 font-medium text-sm">Monthly Requests</h3>
                    <p className="text-4xl font-bold text-white mt-2">{monthlyRequests}</p>
                    <div className="mt-4 text-xs text-purple-400 font-medium">Current billing cycle</div>
                </div>

                {/* Total Usage */}
                <div className="glass-panel p-6 rounded-2xl bg-white/5 border border-white/10 relative overflow-hidden">
                    <h3 className="text-gray-400 font-medium text-sm">Total Lifetime</h3>
                    <p className="text-4xl font-bold text-white mt-2">{totalRequests}</p>
                    <div className="mt-4 text-xs text-gray-400 font-medium">Since inception</div>
                </div>

                {/* DB Storage */}
                <div className="glass-panel p-6 rounded-2xl bg-white/5 border border-white/10 relative overflow-hidden">
                    <h3 className="text-gray-400 font-medium text-sm">Database Storage</h3>
                    <p className="text-4xl font-bold text-white mt-2">{dbUsage?.keys || 0}</p>
                    <div className="mt-4 text-xs text-yellow-400 font-medium">Total Keys Stored</div>
                </div>

                {/* Hot Connections */}

                {/* Hot Connections */}
                <div className="glass-panel p-6 rounded-2xl bg-white/5 border border-white/10 relative overflow-hidden">
                    <h3 className="text-gray-400 font-medium text-sm">Connection Pool</h3>
                    <div className="flex items-baseline gap-2 mt-2">
                        <p className="text-4xl font-bold text-white">{maxHot}</p>
                        <span className="text-gray-500">Sockets Reserved</span>
                    </div>

                    <div className="mt-4 w-full flex items-center gap-2">
                        <div className="h-1.5 flex-1 bg-gray-700 rounded-full overflow-hidden">
                            <div className="bg-green-500 h-full w-full shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                        </div>
                        <span className="text-xs text-green-400 font-medium">Active</span>
                    </div>
                </div>
            </div>

            {/* Live Logs */}
            <div className="glass-panel rounded-2xl p-6 bg-white/5 border border-white/10 min-h-[400px]">
                <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-ping" />
                    Live Traffic
                </h2>
                <div className="space-y-3">
                    {logs.length === 0 ? (
                        <div className="text-gray-500 text-center py-10">No recent activity</div>
                    ) : (
                        [...logs]
                            .sort((a, b) => b.timestamp - a.timestamp) // Sort Newest First
                            .map((log) => (
                                <div key={log.id} className="flex items-center gap-4 text-sm p-3 rounded-lg bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                                    <span className={`font-mono text-xs px-2 py-0.5 rounded ${log.status === 200 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                        {log.status === 200 ? 'SUCCESS' : 'ERROR'}
                                    </span>
                                    <span className="text-blue-300 font-medium min-w-[80px]">{log.model}</span>
                                    <span className="text-gray-300 flex-1 truncate" title={log.preview}>
                                        {log.preview}
                                    </span>
                                    {log.cached && (
                                        <span className="text-yellow-400 text-xs px-2 py-0.5 bg-yellow-400/10 rounded-full">
                                            Cached
                                        </span>
                                    )}
                                    <span className="text-gray-500 text-xs whitespace-nowrap">
                                        {log.duration}ms
                                    </span>
                                    <span className="text-gray-600 text-xs ml-2">
                                        {Math.floor((Date.now() - log.timestamp) / 1000)}s ago
                                    </span>
                                </div>
                            ))
                    )}
                </div>
            </div>
        </main>
    );
}
