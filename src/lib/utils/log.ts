
// Simple Logger Replacement for Vercel/Next.js

export const initLog = () => {
  console.log('Logger initialized (Console mode)');
};

export function newLogger(site?: string, extra?: Record<string, string>) {
  const prefix = site ? `[${site}]` : '';

  return {
    info: (msg: string, ...meta: any[]) => console.log(`${prefix} [INFO]`, msg, ...meta),
    error: (msg: string, ...meta: any[]) => console.error(`${prefix} [ERROR]`, msg, ...meta),
    warn: (msg: string, ...meta: any[]) => console.warn(`${prefix} [WARN]`, msg, ...meta),
    debug: (msg: string, ...meta: any[]) => console.debug(`${prefix} [DEBUG]`, msg, ...meta),
    child: (opts: any) => newLogger(site, { ...extra, ...opts }),
    exitOnError: false
  };
}

export class TraceLogger {
  constructor() { }

  info(msg: string, meta: any) {
    // No-op or console.log
  }
}

export async function SaveMessagesToLogstash(msg: any, other: any = {}) {
  // No-op
}
