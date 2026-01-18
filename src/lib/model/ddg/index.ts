import { Chat, ChatOptions, ChatRequest, ModelType } from '../base';
import {
  ComError,
  Event,
  EventStream,
  parseJSON,
  randomUserAgent,
} from '../../utils';
import { CreateNewAxios } from '../../utils';
import es from 'event-stream';
import { ModelMap } from './define';

export class DDG extends Chat {

  constructor(options?: ChatOptions) {
    super(options);
  }

  support(model: ModelType): number {
    switch (model) {
      case ModelType.Claude3Haiku20240307:
        return 150 * 1000;
      case ModelType.GPT3p5Turbo0125:
        return 150 * 1000;
      case ModelType.LLama_3_70b_chat:
        return 10000;
      case ModelType.Mixtral8x7bInstruct:
        return 10000;
      case ModelType.GPT3p5Turbo: // Added explicit support for default
        return 10000;
      default:
        return 0;
    }
  }

  async preHandle(
    req: ChatRequest,
    options?: {
      token?: boolean;
      countPrompt?: boolean;
      forceRemove?: boolean;
      stream?: EventStream;
    },
  ): Promise<ChatRequest> {
    return super.preHandle(req, {
      token: false,
      countPrompt: true,
      forceRemove: true,
    });
  }

  async chatStream(req: ChatRequest, stream: EventStream): Promise<void> {
    try {
      // Use a fixed, modern User-Agent to avoid detection
      const useragent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

      const commonHeaders = {
        'User-Agent': useragent,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://duckduckgo.com/',
        'Origin': 'https://duckduckgo.com',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
      };

      const client = CreateNewAxios(
        {
          baseURL: 'https://duckduckgo.com',
          headers: commonHeaders,
        },
        { proxy: true },
      );

      console.log("[DDG] Fetching VQD token...");

      let vqd4 = '';
      let cookies: string[] = [];

      // Attempt 3 retries
      for (let i = 0; i < 3; i++) {
        if (vqd4) break;
        if (i > 0) {
          console.log(`[DDG] Retry ${i + 1}...`);
          // Wait briefly before retry
          await new Promise(r => setTimeout(r, 1500));
        }

        // Strategy 1: Status Endpoint
        try {
          const statusRes = await client.get('/duckchat/v1/status', {
            headers: {
              ...commonHeaders,
              'x-vqd-accept': '1',
              // Sometimes Accept-Encoding helps or hurts. Let's stick to standard.
            },
          });
          vqd4 = statusRes.headers['x-vqd-4'];
          if (statusRes.headers['set-cookie']) {
            cookies = [...cookies, ...statusRes.headers['set-cookie']];
          }
          if (vqd4) {
            console.log("[DDG] Strategy 1 (Status) result: Success");
            break;
          }
        } catch (err: any) {
          console.warn("[DDG] Strategy 1 failed:", err.response?.status || err.message);
        }

        // Strategy 2: HTML Fallback (if Strategy 1 failed)
        if (!vqd4) {
          try {
            // Try simpler URL first
            console.log("[DDG] Trying Strategy 2 (HTML Search)...");
            const searchRes = await client.get('/?q=duckduckgo&t=h_&ia=chat', {
              headers: commonHeaders
            });
            const match = searchRes.data.match(/vqd="([\d-]+)"/);
            if (match && match[1]) {
              vqd4 = match[1];
              if (searchRes.headers['set-cookie']) {
                cookies = [...cookies, ...searchRes.headers['set-cookie']];
              }
              console.log("[DDG] Strategy 2 (HTML) result: Success");
              break;
            }
          } catch (err: any) {
            console.warn("[DDG] Strategy 2 failed:", err.message);
          }
        }
      }

      console.log("[DDG] Final VQD:", vqd4);

      if (!vqd4) {
        throw new Error("Failed to get VQD token from DuckDuckGo (All strategies failed). This IP may be blocked.");
      }

      // Small delay to mimic human behavior
      await new Promise(r => setTimeout(r, 500));

      console.log("[DDG] Sending chat request...");

      const cookieHeader = cookies.map(c => c.split(';')[0]).join('; ');

      const res = await client.post(
        '/duckchat/v1/chat',
        {
          model: ModelMap[req.model] || req.model,
          messages: req.messages,
        },
        {
          responseType: 'stream',
          headers: {
            ...commonHeaders,
            'Content-Type': 'application/json',
            'x-vqd-4': vqd4,
            ...(cookieHeader ? { 'Cookie': cookieHeader } : {})
          },
        },
      );

      const pt = res.data.pipe(es.split(/\r?\n\r?\n/)).pipe(
        es.map(async (chunk: any, cb: any) => {
          const res = chunk.toString();
          if (!res) {
            return;
          }
          const dataStr = res.replace('data: ', '');
          // Handle potential JSON parse errors or non-json chunks
          try {
            const data = parseJSON<undefined | { role: string; message: string }>(
              dataStr,
              undefined,
            );
            if (dataStr === '[DONE]') {
              pt.end();
              pt.destroy();
              return;
            }
            cb(null, data);
          } catch (e) {
            cb(null, null);
          }
        }),
      );
      pt.on('data', (data: any) => {
        if (data && data.message) {
          stream.write(Event.message, { content: data.message });
        }
      });
      pt.on('close', () => {
        stream.write(Event.done, { content: '' });
        stream.end();
      });
      pt.on('error', (err: any) => {
        console.error("Stream error in DDG:", err);
        stream.write(Event.error, { error: err.message });
        stream.end();
      });
    } catch (e: any) {
      console.error("[DDG] Fatal Error:", e.message);
      throw new ComError(e.message, ComError.Status.InternalServerError);
    }
  }

  async askStream(req: ChatRequest, stream: EventStream): Promise<void> {
    return this.chatStream(req, stream);
  }
}
