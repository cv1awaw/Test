import { PassThrough, Stream } from 'stream';
import * as crypto from 'crypto';
import es from 'event-stream';
import axios, { AxiosInstance, CreateAxiosDefaults, AxiosError, AxiosResponse } from 'axios';
import HttpsProxyAgent from 'https-proxy-agent';
import { v4 } from 'uuid';
import UserAgent from 'user-agents';
import * as http from 'http';
import * as https from 'https';

// --- Types ---
export enum Event {
  error = 'error',
  message = 'message',
  search = 'search',
  done = 'done',
}

export type ErrorData = { error: string; message?: string; status?: number };
export type MessageData = {
  content: string;
  function_call?: { name: string; arguments: string };
  role?: string;
};
export type Data<T extends Event> = T extends Event.error
  ? ErrorData
  : T extends Event.message
  ? MessageData
  : any;

export type DataCB<T extends Event> = (event: T, data: Data<T>) => void;

// --- Helper Functions ---

export function parseJSON<T>(str: string, defaultObj: T): T {
  try {
    return JSON.parse(str);
  } catch (e: any) {
    return defaultObj;
  }
}

export async function sleep(duration: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(), duration);
  });
}

export function randomUserAgent(): string {
  return new UserAgent().toString();
}

export function randomIP(): string {
  return `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`;
}

export function getTokenCount(input: string): number {
  // Simple approximation: 1 token ~ 4 chars
  return Math.ceil(input.length / 4);
}

// --- EventStream ---

export class EventStream {
  protected readonly pt: PassThrough = new PassThrough();

  constructor() {
    this.pt.setEncoding('utf-8');
  }

  public write<T extends Event>(event: T, data: Data<T>) {
    if (this.pt.writableEnded) {
      return;
    }
    this.pt.write(`event: ${event}\n`, 'utf-8');
    this.pt.write(`data: ${JSON.stringify(data)}\n\n`, 'utf-8');
  }

  stream() {
    return this.pt;
  }

  end(cb?: () => void) {
    this.pt.end(cb);
  }

  public read(dataCB: DataCB<Event>, closeCB: () => void) {
    this.pt.setEncoding('utf-8');
    this.pt.pipe(es.split('\n\n')).pipe(
      es.map(async (chunk: any, cb: any) => {
        const res = chunk.toString();
        if (!res) {
          return;
        }
        const [eventStr, dataStr] = res.split('\n');
        const event: Event = eventStr.replace('event: ', '') as Event;

        const data = parseJSON(
          dataStr.replace('data: ', ''),
          {} as Data<Event>,
        );
        dataCB(event, data);
        cb(null, chunk); // Fix for es.map to continue
      }),
    );
    this.pt.on('close', closeCB);
  }
}

// --- ComError ---

export class ComError extends Error {
  public status: number;
  public data?: any;

  static Status = {
    BadRequest: 400,
    ParamsError: 422,
    Unauthorized: 401,
    Forbidden: 403,
    NotFound: 404,
    InternalServerError: 500,
    RequestTooLarge: 413,
  };

  constructor(
    message?: string,
    code: number = ComError.Status.InternalServerError,
    data?: any,
  ) {
    super(message);
    this.name = this.constructor.name;
    this.status = code;
    this.data = data;
  }
}

// --- Axios Helpers (Moved from proxyAgent.ts) ---

const tunnel = require('tunnel'); // Requires 'tunnel' package

export const getProxy = () => {
  return process.env.http_proxy || '';
};

export function getHostPortFromURL(url: string) {
  try {
    const u = new URL(url);
    return [u.hostname, parseInt(u.port || (u.protocol === 'https:' ? '443' : '80'))];
  } catch (e) {
    return ['', 0];
  }
}

// Global shared agents to reuse TCP connections
// usage of 'lifo' scheduling ensures the most recently used (and thus most likely active) socket is used first
const agentOptions = {
  keepAlive: true,
  scheduling: 'lifo' as 'lifo', // explicit cast for TS check if needed, but 'lifo' string usually works
  timeout: 120000, // 2 minutes connection timeout
  freeSocketTimeout: 120000, // 2 minutes free socket timeout (prevents stale connections)
  keepAliveMsecs: 120000, // 2 minutes keep-alive packet delay
  maxSockets: Infinity, // Allow unlimited concurrent connections
  maxFreeSockets: 5, // Maintain 5 free sockets for "hot" connections as requested
};

const sharedHttpAgent = new http.Agent(agentOptions);
const sharedHttpsAgent = new https.Agent(agentOptions);

export function CreateNewAxios(
  config: CreateAxiosDefaults,
  options?: {
    proxy?: string | boolean | undefined;
    errorHandler?: (error: AxiosError) => void;
  },
) {
  const { proxy, errorHandler } = options || {};
  const createConfig: CreateAxiosDefaults = { timeout: 60 * 1000, ...config };
  createConfig.proxy = false;

  if (proxy) {
    const realProxy = proxy === true ? getProxy() : proxy;
    if (typeof realProxy === 'string' && realProxy) {
      // Simple proxy support via https-proxy-agent or tunnel
      // For simplicity in this env, we try to use basic config or agent
      // If tunnel is problematic on Vercel, we might skip it, but let's keep it for now.
      const [host, port] = getHostPortFromURL(realProxy);
      createConfig.httpsAgent = tunnel.httpsOverHttp({
        proxy: { host, port },
      });
      createConfig.httpAgent = tunnel.httpOverHttp({
        proxy: { host, port },
      });
    }
  } else {
    // No proxy, use shared keep-alive agents
    createConfig.httpAgent = sharedHttpAgent;
    createConfig.httpsAgent = sharedHttpsAgent;
  }

  const instance = axios.create(createConfig);

  if (errorHandler) {
    instance.interceptors.response.use(
      (response) => response,
      (error) => {
        errorHandler(error);
        return Promise.reject(error);
      },
    );
  }

  return instance;
}

// --- Missing Utils Stubs ---

export function extractHttpFileURLs(text: string): string[] {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  return text.match(urlRegex) || [];
}

export function extractHttpImageFileURLs(text: string): string[] {
  const urlRegex = /(https?:\/\/[^\s]+\.(?:png|jpg|jpeg|gif|webp))/gi;
  return text.match(urlRegex) || [];
}

export function removeRandomChars(text: string, percentage: number): string {
  return text; // No-op for now to keep it simple
}

export function colorLabel(label: string): string {
  return label;
}

export function getConnectionStats() {
  return {
    activeConnections: (Object.values(sharedHttpAgent.sockets).flat().length) + (Object.values(sharedHttpsAgent.sockets).flat().length),
    idleConnections: (Object.values(sharedHttpAgent.freeSockets).flat().length) + (Object.values(sharedHttpsAgent.freeSockets).flat().length),
    waitingRequests: (Object.values(sharedHttpAgent.requests).flat().length) + (Object.values(sharedHttpsAgent.requests).flat().length),
    maxFreeSockets: agentOptions.maxFreeSockets
  };
}
