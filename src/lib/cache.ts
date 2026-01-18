import { Redis } from '@upstash/redis';

// Interface for our Cache to support both Sync (Memory) and Async (Redis) transparently
// We will make all methods async to satisfy the Redis requirement
interface ACache<T> {
    get(key: string): Promise<T | undefined>;
    set(key: string, value: T, ttlSeconds?: number): Promise<void>;
    has(key: string): Promise<boolean>;
}

// 1. In-Memory Implementation (Fallback)
class MemoryCache<T> implements ACache<T> {
    private cache: Map<string, { value: T; expiry: number }>;
    private limit: number;

    constructor(limit: number = 1000) {
        this.cache = new Map();
        this.limit = limit;
    }

    async get(key: string): Promise<T | undefined> {
        const item = this.cache.get(key);
        if (!item) return undefined;

        if (Date.now() > item.expiry) {
            this.cache.delete(key);
            return undefined;
        }

        return item.value;
    }

    async set(key: string, value: T, ttlSeconds: number = 60 * 60 * 24 * 30): Promise<void> { // Default 30 days
        if (this.cache.size >= this.limit) {
            const firstKey = this.cache.keys().next().value;
            if (firstKey) this.cache.delete(firstKey);
        }

        const expiry = ttlSeconds <= 0 ? Infinity : Date.now() + ttlSeconds * 1000;

        this.cache.set(key, {
            value,
            expiry,
        });
    }

    async has(key: string): Promise<boolean> {
        return (await this.get(key)) !== undefined;
    }
}

// 2. Redis Implementation (Persistent)
class RedisCache<T> implements ACache<T> {
    private redis: Redis;

    constructor() {
        // Vercel Storage integration injects 'KV_REST_API_URL' and 'KV_REST_API_TOKEN'
        // We explicitly use them here to ensure connection success.
        this.redis = new Redis({
            url: process.env.KV_REST_API_URL!,
            token: process.env.KV_REST_API_TOKEN!,
        });
    }

    private async retry<R>(operation: () => Promise<R>, retries: number = 3): Promise<R> {
        for (let i = 0; i < retries; i++) {
            try {
                return await operation();
            } catch (error) {
                if (i === retries - 1) throw error;
                const delay = Math.pow(2, i) * 100; // Exponential backoff: 100ms, 200ms, 400ms
                console.warn(`[Redis] Operation failed, retrying in ${delay}ms...`, error);
                await new Promise(res => setTimeout(res, delay));
            }
        }
        throw new Error("Unreachable");
    }

    async get(key: string): Promise<T | undefined> {
        try {
            return await this.retry(async () => {
                try {
                    console.log(`[Redis] GET ${key.slice(0, 20)}...`);
                    const start = Date.now();
                    const data = await this.redis.get<T>(key);
                    console.log(`[Redis] GET result in ${Date.now() - start}ms:`, data ? 'HIT' : 'MISS');
                    return data === null ? undefined : data;
                } catch (e) {
                    console.error("[Redis] GET Error (will retry):", e);
                    throw e; // Re-throw to trigger retry
                }
            });
        } catch (finalError) {
            // CRITICAL OPTIMIZATION: If all retries fail, return undefined (treat as cache miss)
            // instead of crashing the request. This ensures the user still gets an answer.
            console.error("[Redis] GET Failed after retries. Falling back to fresh generation.", finalError);
            return undefined;
        }
    }

    async set(key: string, value: T, ttlSeconds: number = 60 * 60 * 24 * 30): Promise<void> {
        try {
            await this.retry(async () => {
                console.log(`[Redis] SET ${key.slice(0, 20)}... (TTL: ${ttlSeconds > 0 ? ttlSeconds + 's' : 'FOREVER'})`);
                if (ttlSeconds > 0) {
                    await this.redis.set(key, value, { ex: ttlSeconds });
                } else {
                    await this.redis.set(key, value); // No expiry (stored forever)
                }
                console.log(`[Redis] SET success`);
            });
        } catch (e) {
            console.error("[Redis] SET Error after retries:", e);
        }
    }

    async has(key: string): Promise<boolean> {
        try {
            return await this.retry(async () => {
                const exists = await this.redis.exists(key);
                return exists === 1;
            });
        } catch (e) {
            console.error("[Redis] HAS Error after retries:", e);
            return false;
        }
    }
}

// Factory to decide which cache to use
function createCache(): ACache<string> {
    if (process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN) {
        console.log("🔥 Using Persistent Redis Cache");
        return new RedisCache<string>();
    } else {
        console.log("⚠️ Redis not configured. Using In-Memory Fallback Cache.");
        return new MemoryCache<string>(5000);
    }
}

export const responseCache = createCache();
