"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Trash2, StopCircle, Network } from "lucide-react";
import mermaid from "mermaid";

type Message = {
    role: "user" | "assistant";
    content: string;
};

export default function PlaygroundPage() {
    const [messages, setMessages] = useState<Message[]>([
        { role: "assistant", content: "Hello! I am ChatGPT 5. How can I help you today?" }
    ]);
    const [input, setInput] = useState("");
    const [model, setModel] = useState("gpt-5");
    const [loading, setLoading] = useState(false);
    const [showMindMap, setShowMindMap] = useState(false);
    const [mindMapContent, setMindMapContent] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        mermaid.initialize({ startOnLoad: true, theme: 'dark' });
    }, []);

    useEffect(() => {
        if (showMindMap && mindMapContent) {
            mermaid.contentLoaded();
        }
    }, [showMindMap, mindMapContent]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage = { role: "user" as const, content: input };
        setMessages(prev => [...prev, userMessage]);
        setInput("");
        setLoading(true);

        const assistantMessageIdx = messages.length + 1; // Index of the new assistant message
        setMessages(prev => [...prev, { role: "assistant", content: "" }]); // Placeholder

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-client-source": "web-playground"
                },
                body: JSON.stringify({
                    model: model,
                    messages: [...messages, userMessage].map(m => ({ role: m.role, content: m.content })),
                    stream: true
                }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || "Failed to fetch response");
            }

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            let currentContent = "";

            while (!done) {
                const { value, done: doneReading } = await reader.read();
                done = doneReading;
                const chunkValue = decoder.decode(value, { stream: true });

                // Parse server-sent events
                const lines = chunkValue.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') continue;
                        try {
                            const data = JSON.parse(dataStr);
                            // Handle custom event format from route.ts: { event, data: { content } }
                            if (data.event === 'message' && data.data?.content) {
                                currentContent += data.data.content;
                                setMessages(prev => {
                                    const newMessages = [...prev];
                                    if (newMessages[assistantMessageIdx]) {
                                        newMessages[assistantMessageIdx] = {
                                            ...newMessages[assistantMessageIdx],
                                            content: currentContent
                                        };
                                    }
                                    return newMessages;
                                });
                            } else if (data.event === 'error') {
                                throw new Error(data.data?.error || "Stream error");
                            }
                        } catch (e) {
                            // Ignore parse errors for partial chunks
                        }
                    }
                }

                // EXTRACT MERMAID IF EXISTS
                // Simple heuristic: look for ```mermaid ... ```
                const mermaidMatch = currentContent.match(/```mermaid([\s\S]*?)```/);
                if (mermaidMatch) {
                    setMindMapContent(mermaidMatch[1].trim());
                }
            }

        } catch (error: any) {
            setMessages(prev => {
                const newMessages = [...prev];
                // If we have partial content, append error? Or just replace?
                // Replacing for clarity if content is empty, appending if not.
                const lastMsg = newMessages[assistantMessageIdx];

                let errorMsg = error.message;
                // User-friendly message for the empty content error
                if (errorMsg.includes("Stream ended without content")) {
                    errorMsg = "The model returned an empty response. Please try again.";
                }

                if (lastMsg) {
                    newMessages[assistantMessageIdx] = {
                        role: "assistant",
                        content: lastMsg.content ? `${lastMsg.content}\n[Error: ${errorMsg}]` : `Error: ${errorMsg}`
                    };
                }
                return newMessages;
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <main className="min-h-screen pt-24 pb-4 px-4 sm:px-8 relative overflow-hidden flex flex-col items-center">
            {/* Background Decor */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none -z-10">
                <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/5 rounded-full blur-[120px]" />
                <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-600/5 rounded-full blur-[120px]" />
            </div>

            <div className="max-w-4xl w-full flex-1 flex flex-col glass-panel rounded-2xl border border-white/10 shadow-2xl overflow-hidden h-[80vh]">

                {/* Header */}
                <div className="p-4 border-b border-white/10 bg-black/20 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                        <h1 className="font-semibold text-white">API Playground</h1>
                        <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-gray-400 border border-white/5">{model}</span>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowMindMap(!showMindMap)}
                            className={`p-2 rounded-lg transition-colors ${showMindMap ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-white/10 text-gray-400'}`}
                            title="Toggle Mind Map"
                        >
                            <Network size={18} />
                        </button>
                        <button
                            onClick={() => setMessages([{ role: "assistant", content: "Chat cleared. Ready for new requests!" }])}
                            className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-red-400 transition-colors"
                            title="Clear Chat"
                        >
                            <Trash2 size={18} />
                        </button>
                    </div>
                </div>

                {/* Main Content Area */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Chat Area */}
                    <div className={`flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent ${showMindMap ? 'w-1/2 border-r border-white/10' : 'w-full'}`}>
                        {messages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`flex gap-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                            >
                                <div className={`
                    max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed
                    ${msg.role === "user"
                                        ? "bg-blue-600/20 border border-blue-500/30 text-white rounded-tr-sm"
                                        : "bg-white/5 border border-white/10 text-gray-300 rounded-tl-sm"}
                  `}>
                                    <div className="flex items-center gap-2 mb-1 opacity-50 text-xs font-medium uppercase tracking-wider">
                                        {msg.role === "user" ? <User size={12} /> : <Bot size={12} />}
                                        {msg.role}
                                    </div>
                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex gap-4 justify-start">
                                <div className="bg-white/5 border border-white/10 text-gray-300 rounded-2xl rounded-tl-sm p-4 flex items-center gap-2">
                                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-100" />
                                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-200" />
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Mind Map Area */}
                    {showMindMap && (
                        <div className="flex-1 bg-black/40 p-4 overflow-auto flex flex-col">
                            <div className="mb-4 flex justify-between items-center">
                                <h3 className="text-white font-medium">Mind Map Visualization</h3>
                                <button
                                    onClick={() => {
                                        const prompt = "Please create a detailed mind map of our conversation so far using Mermaid.js syntax. Output ONLY the code block starting with ```mermaid and ending with ```.";
                                        setInput(prompt);
                                        // Auto-submit hack: We can't easily call handleSend(e) without an event, 
                                        // so we'll just set the input and let the user click send, OR we can try to automate it.
                                        // Better UX: modify message state directly? No, we need the API response.
                                        // Let's just set input and focus.
                                    }}
                                    className="text-xs bg-blue-600 px-3 py-1 rounded text-white hover:bg-blue-500 flex items-center gap-1"
                                >
                                    <Network size={12} />
                                    Generate Map
                                </button>
                            </div>
                            <div className="mermaid flex-1 flex items-center justify-center">
                                {mindMapContent || "No mind map data. Ask the AI to generate a Mermaid Mindmap."}
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="p-4 bg-black/20 border-t border-white/10">
                    <form onSubmit={handleSend} className="relative">
                        <div className="flex gap-2">
                            <select
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                className="bg-black/40 border border-white/10 rounded-xl px-4 py-4 text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 cursor-pointer"
                                disabled={loading}
                            >
                                <option value="gpt-5">ChatGPT 5 (Latest)</option>
                                <option value="gpt-4o">GPT-4o (OpenAI)</option>
                                <option value="mistral">Mistral (Fast & Smart)</option>
                                <option value="gemini">Gemini (Google)</option>
                                <option value="openai">OpenAI (Standard)</option>
                            </select>
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Type your message..."
                                className="flex-1 bg-black/40 border border-white/10 rounded-xl pl-4 pr-14 py-4 text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                                disabled={loading}
                            />
                            <button
                                type="submit"
                                disabled={loading || !input.trim()}
                                className="p-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl disabled:opacity-50 disabled:bg-gray-700 transition-colors"
                            >
                                {loading ? <StopCircle size={20} /> : <Send size={20} />}
                            </button>
                        </div>
                    </form>
                    <div className="text-center mt-2">
                        <span className="text-xs text-gray-600">This playground uses your local /api/chat endpoint.</span>
                    </div>
                </div>

            </div>
        </main>
    );
}
