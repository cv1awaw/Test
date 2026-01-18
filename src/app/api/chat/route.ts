import * as nodeCrypto from 'crypto';
import { NextResponse } from "next/server";
import { chatModel } from "@/lib/model";
import { Site, ModelType, Message } from "@/lib/model/base";
import { EventStream, Event } from "@/lib/utils";
import { responseCache } from "@/lib/cache"; // Import the cache
import { statsManager } from "@/lib/stats";

// Helper to convert internal EventStream to Web ReadableStream
function eventStreamToReadableStream(eventStream: EventStream): ReadableStream {
    return new ReadableStream({
        start(controller) {
            eventStream.read(
                (event, data) => {
                    const payload = { event, data };
                    controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(payload)}\n\n`));
                },
                () => {
                    controller.close();
                }
            );
        },
        cancel() {
            // Handle cancellation if needed
        },
    });
}

// Helper: Simulate a stream from a cached string
function createCachedStream(cachedText: string): ReadableStream {
    return new ReadableStream({
        start(controller) {
            const payload = { event: 'message', data: { content: cachedText, role: 'assistant' } };
            controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(payload)}\n\n`));

            const donePayload = { event: 'done', data: { content: '' } };
            controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(donePayload)}\n\n`));
            controller.close();
        }
    });
}

// CORS Headers helper
const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-client-source, x-requested-with, accept, origin',
};

export async function OPTIONS() {
    return NextResponse.json({}, { headers: corsHeaders });
}

export async function POST(request: Request) {
    const start = Date.now();
    try {
        const body = await request.json();
        const { model, messages, stream } = body;
        // Default: Log everything. Exclude ONLY the internal playground if desired.
        // User requested: "not the ground play chcaht" -> Exclude playground.
        // "focus on the api" -> Include everything else (external calls with no headers).
        const source = request.headers.get('x-client-source');
        // LOGGING FIX: User wants to see ALL traffic in the dashboard, including playground tests.
        const shouldLog = true;

        // --- 1. MODEL MAPPING & NORMALIZATION ---
        const modelMapping: { [key: string]: string } = {
            'gpt-4o': 'openai',
            'gpt-3.5-turbo': 'openai',
            'gpt-5': 'openai',
            'chatgpt-5': 'openai',
            'claude': 'mistral',
            'mistral': 'mistral',
            'gemini': 'gemini',
            'openai': 'openai'
        };

        const requestedModel = (model as string || 'gpt-4o').toLowerCase().trim();
        const targetModel = modelMapping[requestedModel] || requestedModel;

        const normalizeText = (text: string) => {
            return (text || "").trim().toLowerCase().replace(/\s+/g, ' ');
        };

        // Capture Prompt for Logging
        const prompt = messages[messages.length - 1].content as string;

        // --- 2. CACHE CHECK ---
        const normalizedMessages = messages.map((m: any) => ({
            role: m.role,
            content: normalizeText(m.content)
        }));

        // STABILIZATION: Determine Key explicitly and HASH it
        const keyObject = {
            model: targetModel,
            messages: normalizedMessages
        };
        const keyString = JSON.stringify(keyObject);
        // Use SHA-256 for a consistent, safe Redis Key
        const keyHash = nodeCrypto.createHash('sha256').update(keyString).digest('hex');
        const cacheKey = `chat:${keyHash}`;

        console.log(`[READ_CACHE] Checking Hash: ${keyHash}`);
        console.log(`[CACHE_DEBUG] Context Depth: ${messages.length} messages. Last User Prompt: "${prompt.slice(0, 20)}..."`);

        // OPTIMIZATION: Single round-trip to Redis. 
        // If it fails or misses, it returns undefined, and we proceed to generate.
        const cachedResponse = await responseCache.get(cacheKey);

        if (cachedResponse) {
            console.log(`[CACHE HIT] Instant response for Hash: ${keyHash}`);
            // Log Cache Hit
            if (shouldLog) {
                statsManager.incrementRequest(targetModel, 200, Date.now() - start, true, prompt);
            }

            if (stream) {
                return new Response(createCachedStream(cachedResponse), {
                    headers: {
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        ...corsHeaders,
                    },
                });
            } else {
                const openAIResponse = {
                    id: 'chatcmpl-cached-' + Math.random().toString(36).substr(2, 9),
                    object: 'chat.completion',
                    created: Date.now(),
                    model: targetModel,
                    choices: [
                        {
                            index: 0,
                            message: { role: 'assistant', content: cachedResponse },
                            finish_reason: 'stop',
                        },
                    ],
                    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
                };
                return NextResponse.json(openAIResponse, { headers: corsHeaders });
            }
        }
        // --- END CACHE CHECK ---


        // --- 3. PROVIDER SETUP ---
        const site = Site.Pollinations;
        const chatInstance = chatModel.get(site);

        if (!chatInstance) {
            if (shouldLog) {
                statsManager.incrementRequest(targetModel, 404, Date.now() - start, false, prompt);
            }
            return NextResponse.json({ error: "Provider not found" }, { status: 404 });
        }

        const reqData = {
            prompt: messages[messages.length - 1].content as string,
            model: targetModel as ModelType,
            messages: messages as Message[],
        };

        if (stream) {
            const internalStream = new EventStream();

            // Capture stream content for caching
            let fullContent = "";
            const originalWrite = internalStream.write.bind(internalStream);
            internalStream.write = (event: Event, data: any) => {
                // Debug: Log every chunk to see structure
                // console.log(`[STREAM_DEBUG] Event: ${event}, Keys: ${Object.keys(data || {})}`);

                if (event === Event.message) {
                    if (data && typeof data === 'object') {
                        if (data.content) {
                            fullContent += data.content;
                        } else if (data.delta && data.delta.content) {
                            // Handle OpenAI style delta if present (safeguard)
                            fullContent += data.delta.content;
                        }
                    }
                }
                originalWrite(event, data);
            };
            const originalEnd = internalStream.end.bind(internalStream);
            internalStream.end = (cb) => {
                console.log(`[STREAM_END] Closing stream. FullContent Length: ${fullContent.length}`); // Debug log
                if (fullContent) {
                    console.log(`[WRITE_CACHE] Saving Hash: ${keyHash} (Length: ${fullContent.length})`);
                    // PROMISE CHAIN: Ensure set completes (or fails safely) before closing stream
                    // Pass -1 to indicate NO EXPIRY (Forever Cache)
                    responseCache.set(cacheKey, fullContent, -1)
                        .then(() => console.log("[WRITE_CACHE_SUCCESS]"))
                        .catch(err => console.error("[WRITE_CACHE_ERROR]", err))
                        .finally(() => {
                            originalEnd(cb);
                        });
                } else {
                    console.warn(`[WRITE_SKIPPED] Empty content for Hash: ${keyHash}. Check stream data structure.`);
                    originalEnd(cb);
                }
            };

            // Log Start of Stream
            if (shouldLog) {
                statsManager.incrementRequest(targetModel, 200, Date.now() - start, false, prompt);
            }

            chatInstance.askStream(reqData, internalStream).catch(err => {
                console.error("Stream error:", err);
                internalStream.write(Event.error, { error: err.message });
                internalStream.end();
            });

            const readable = eventStreamToReadableStream(internalStream);
            return new Response(readable, {
                headers: {
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    ...corsHeaders,
                },
            });
        } else {
            const response = await chatInstance.ask(reqData);

            if (response.error) {
                throw new Error(response.error);
            }

            // --- CACHE SAVE ---
            if (response.content) {
                // Pass -1 for Infinite Cache
                await responseCache.set(cacheKey, response.content, -1);
            }

            // Log Success
            if (shouldLog) {
                statsManager.incrementRequest(targetModel, 200, Date.now() - start, false, prompt);
            }

            const openAIResponse = {
                id: 'chatcmpl-' + Math.random().toString(36).substr(2, 9),
                object: 'chat.completion',
                created: Date.now(),
                model: targetModel,
                choices: [
                    {
                        index: 0,
                        message: {
                            role: response.role || 'assistant',
                            content: response.content || '',
                        },
                        finish_reason: 'stop',
                    },
                ],
                usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
            };
            return NextResponse.json(openAIResponse, { headers: corsHeaders });
        }

    } catch (error: any) {
        console.error("API Error:", error);
        // We can't easily check header here if request failed before parsing, 
        // but try/catch block is inside POST so we have request object. 
        // We moved isWebPlayground extraction inside try, so checking header directly again if needed
        const source = request.headers.get('x-client-source');
        const shouldLog = source === 'web-playground' || source === 'external-website';
        if (shouldLog) {
            statsManager.incrementRequest("unknown", 500, Date.now() - start, false, "Error");
        }
        return NextResponse.json(
            { error: error.message || "Internal Server Error" },
            { status: 500, headers: corsHeaders }
        );
    }
}
