import { Chat, ChatOptions, ChatRequest, ModelType } from '../base';
import {
    ComError,
    Event,
    EventStream,
} from '../../utils';
import { CreateNewAxios } from '../../utils';
import es from 'event-stream';

export class Pollinations extends Chat {

    private client: any;

    constructor(options?: ChatOptions) {
        super(options);
        this.client = CreateNewAxios({
            baseURL: 'https://text.pollinations.ai',
        });
    }

    support(model: ModelType): number {
        return 100000; // Supports broadly
    }

    async preHandle(req: ChatRequest): Promise<ChatRequest> {
        return super.preHandle(req, {
            token: false,
            countPrompt: false,
            forceRemove: false,
        });
    }

    async askStream(req: ChatRequest, stream: EventStream): Promise<void> {
        try {
            // Convert messages to simple text or keep standard format if supported
            // Pollinations supports OpenAI-like messages array in POST

            const res = await this.client.post('/', {
                messages: req.messages,
                model: req.model || 'openai', // Pass the requested model (e.g. 'claude', 'gpt-4o', 'mistral')
                stream: false // Pollinations streaming is raw text, let's treat it as non-stream for simplicity first or handle raw stream
            }, {
                responseType: 'stream'
            });

            // Pollinations stream is just raw text chunks, not "data: json" events usually
            res.data.on('data', (chunk: any) => {
                const text = chunk.toString();
                stream.write(Event.message, { content: text });
            });

            res.data.on('end', () => {
                stream.write(Event.done, { content: '' });
                stream.end();
            });

            res.data.on('error', (err: any) => {
                stream.write(Event.error, { error: err.message });
                stream.end();
            });

        } catch (e: any) {
            console.error("[Pollinations] Error:", e.message);
            throw new ComError(e.message, ComError.Status.InternalServerError);
        }
    }
}
