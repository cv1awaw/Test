import { Redis } from '@upstash/redis';

export interface RequestLog {
    id: string;
    timestamp: number;
    model: string;
    status: number;
    duration: number; // ms
    cached: boolean;
    preview: string; // First 50 chars of prompt
}

export interface Stats {
    dailyRequests: number;
    monthlyRequests: number;
    totalRequests: number;
    requestsByModel: Record<string, number>;
    logs: RequestLog[];
}

class StatsManager {
    private redis: Redis | null = null;
    private inMemoryStats: Stats = {
        dailyRequests: 0,
        monthlyRequests: 0,
        totalRequests: 0,
        requestsByModel: {},
        logs: []
    };
    private readonly LOG_LIMIT = 50;

    constructor() {
        if (process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN) {
            this.redis = new Redis({
                url: process.env.KV_REST_API_URL,
                token: process.env.KV_REST_API_TOKEN,
            });
        }
    }

    private getDateKey(): string {
        return new Date().toISOString().split('T')[0]; // "YYYY-MM-DD"
    }

    private getMonthKey(): string {
        return new Date().toISOString().slice(0, 7); // "YYYY-MM"
    }

    async incrementRequest(model: string, status: number, duration: number, cached: boolean, prompt: string) {
        const dateKey = this.getDateKey();
        const monthKey = this.getMonthKey();

        // Update In-Memory (Always do this for immediate UI feedback)
        this.inMemoryStats.dailyRequests++;
        this.inMemoryStats.monthlyRequests++;
        this.inMemoryStats.totalRequests++;
        this.inMemoryStats.requestsByModel[model] = (this.inMemoryStats.requestsByModel[model] || 0) + 1;

        const log: RequestLog = {
            id: Math.random().toString(36).substring(7),
            timestamp: Date.now(),
            model,
            status,
            duration,
            cached,
            preview: prompt.slice(0, 50) + (prompt.length > 50 ? '...' : '')
        };

        this.inMemoryStats.logs.unshift(log);
        if (this.inMemoryStats.logs.length > this.LOG_LIMIT) {
            this.inMemoryStats.logs.pop();
        }

        // Persist to Redis if available
        if (this.redis) {
            try {
                const p = this.redis.pipeline();
                p.incr(`stats:daily:${dateKey}`);
                p.incr(`stats:monthly:${monthKey}`);
                p.incr(`stats:total`);
                p.hincrby(`stats:models`, model, 1);

                // Persist logs to Redis (maintain last 50)
                // We serialize the log object to string to store in Redis List
                p.lpush(`stats:logs`, JSON.stringify(log));
                p.ltrim(`stats:logs`, 0, this.LOG_LIMIT - 1);

                await p.exec();
            } catch (e) {
                console.error("Failed to update Redis stats:", e);
            }
        }
    }

    async getStats(): Promise<Stats> {
        if (this.redis) {
            try {
                const dateKey = this.getDateKey();
                const monthKey = this.getMonthKey();

                const [daily, monthly, total, models, logs] = await Promise.all([
                    this.redis.get<number>(`stats:daily:${dateKey}`),
                    this.redis.get<number>(`stats:monthly:${monthKey}`),
                    this.redis.get<number>(`stats:total`),
                    this.redis.hgetall<Record<string, number>>(`stats:models`),
                    this.redis.lrange<string>(`stats:logs`, 0, this.LOG_LIMIT - 1)
                ]);

                // Parse logs from Redis strings back to objects
                const parsedLogs: RequestLog[] = (logs || []).map(logStr => {
                    try {
                        return typeof logStr === 'string' ? JSON.parse(logStr) : logStr;
                    } catch (e) {
                        return null;
                    }
                }).filter(Boolean) as RequestLog[];

                // Sync basic counts back to memory for consistency in mixed environments
                return {
                    dailyRequests: daily || 0,
                    monthlyRequests: monthly || 0,
                    totalRequests: total || 0,
                    requestsByModel: models || {},
                    logs: parsedLogs.length > 0 ? parsedLogs : this.inMemoryStats.logs
                };
            } catch (e) {
                console.error("Failed to fetch Redis stats, returning in-memory fallback:", e);
                return this.inMemoryStats;
            }
        }
        return this.inMemoryStats;
    }

    async getDbUsage(): Promise<{ keys: number }> {
        if (this.redis) {
            try {
                // Approximate usage by counting all keys matching 'stats:*' or just dbsize
                const size = await this.redis.dbsize();
                return { keys: size };
            } catch (e) {
                console.error("Failed to get DB size:", e);
                return { keys: 0 };
            }
        }
        return { keys: 0 };
    }

    async flushAll(): Promise<void> {
        console.log("Flushing All Data...");
        if (this.redis) {
            try {
                await this.redis.flushdb();
            } catch (e) {
                console.error("Failed to flush DB:", e);
                throw e;
            }
        }

        // Reset in-memory
        this.inMemoryStats = {
            dailyRequests: 0,
            monthlyRequests: 0,
            totalRequests: 0,
            requestsByModel: {},
            logs: []
        };
    }
}

export const statsManager = new StatsManager();
