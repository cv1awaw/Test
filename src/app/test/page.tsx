"use client";

import { useState, useEffect } from "react";
import { Send, Globe, Youtube, MessageSquare, Network, Sparkles, CheckCircle, AlertCircle } from "lucide-react";
import mermaid from "mermaid";

export default function TestPage() {
    // Translator State
    const [transText, setTransText] = useState("");
    const [transTarget, setTransTarget] = useState("es");
    const [transResult, setTransResult] = useState("");
    const [transLoading, setTransLoading] = useState(false);

    // YouTube State
    const [ytUrl, setYtUrl] = useState("");
    const [ytResult, setYtResult] = useState("");
    const [ytLoading, setYtLoading] = useState(false);

    // Mind Map State
    const [mmInput, setMmInput] = useState("");
    const [mmResult, setMmResult] = useState("");
    const [mmLoading, setMmLoading] = useState(false);

    useEffect(() => {
        mermaid.initialize({ startOnLoad: true, theme: 'dark' });
    }, []);

    useEffect(() => {
        if (mmResult && mmResult.startsWith('graph') || mmResult.startsWith('mindmap')) {
            const renderMap = async () => {
                try {
                    // Force re-render of mermaid diagram
                    const element = document.getElementById("mermaid-test-output");
                    if (element) {
                        element.removeAttribute('data-processed');
                        element.innerHTML = mmResult;
                        await mermaid.run({ nodes: [element] });
                    }
                } catch (e) {
                    console.error("Mermaid Render Error", e);
                }
            }
            renderMap();
        }
    }, [mmResult]);

    const handleTranslate = async () => {
        setTransLoading(true);
        try {
            const res = await fetch("/api/translate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: transText, target: transTarget })
            });
            const data = await res.json();
            setTransResult(data.translatedText || data.error);
        } catch (e: any) {
            setTransResult("Error: " + e.message);
        }
        setTransLoading(false);
    };

    const handleYoutube = async () => {
        setYtLoading(true);
        try {
            const res = await fetch("/api/youtube", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: ytUrl })
            });
            const data = await res.json();
            setYtResult(data.transcript || data.error);
        } catch (e: any) {
            setYtResult("Error: " + e.message);
        }
        setYtLoading(false);
    };

    const handleMindMap = async () => {
        setMmLoading(true);
        setMmResult("");
        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: "gpt-5",
                    messages: [
                        { role: "system", content: "You are a Mind Map Generator. Output ONLY valid Mermaid.js DOM syntax code starting with `graph TD` or `mindmap`. Do not include markdown code ticks." },
                        { role: "user", content: `Create a simple mind map about: ${mmInput}` }
                    ],
                    stream: false // easier to handle for test
                })
            });
            const data = await res.json();
            let content = data.choices?.[0]?.message?.content || "";

            // Cleanup markdown if present
            content = content.replace(/```mermaid/g, "").replace(/```/g, "").trim();

            setMmResult(content);
        } catch (e: any) {
            setMmResult("Error: " + e.message);
        }
        setMmLoading(false);
    };

    return (
        <main className="min-h-screen bg-neutral-950 text-white p-6 sm:p-12 relative overflow-hidden">
            {/* Ambient Background */}
            <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[120px] -z-10" />
            <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-[120px] -z-10" />

            <header className="max-w-6xl mx-auto mb-16 space-y-4">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20">
                    <Sparkles size={12} />
                    <span>System Status: Online</span>
                </div>
                <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
                    API <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">Feature Tests</span>
                </h1>
                <p className="text-lg text-gray-400 max-w-2xl">
                    Verify the functionality of newly integrated modules: Neural Translation, Content Extraction, and Structural Visualization.
                </p>
            </header>

            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* 1. Translator Card */}
                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl relative group hover:border-blue-500/30 transition-all">
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/0 to-purple-500/0 group-hover:from-blue-500/20 group-hover:to-purple-500/20 rounded-3xl opacity-0 group-hover:opacity-100 transition-all blur-md -z-10" />

                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-3 bg-blue-500/20 rounded-xl text-blue-400">
                            <Globe size={24} />
                        </div>
                        <h2 className="text-2xl font-semibold">Translator</h2>
                    </div>

                    <div className="space-y-4">
                        <textarea
                            className="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-gray-200 focus:outline-none focus:border-blue-500/50 min-h-[120px]"
                            placeholder="Enter text to translate..."
                            value={transText}
                            onChange={e => setTransText(e.target.value)}
                        />
                        <div className="flex gap-3">
                            <select
                                className="bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-gray-300 focus:outline-none"
                                value={transTarget}
                                onChange={e => setTransTarget(e.target.value)}
                            >
                                <option value="es">Spanish</option>
                                <option value="fr">French</option>
                                <option value="de">German</option>
                                <option value="ja">Japanese</option>
                                <option value="zh">Chinese</option>
                            </select>
                            <button
                                onClick={handleTranslate}
                                disabled={transLoading}
                                className="flex-1 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2"
                            >
                                {transLoading ? "Processing..." : "Translate Text"}
                            </button>
                        </div>
                    </div>
                    {transResult && (
                        <div className="mt-6 p-4 bg-black/40 rounded-xl border border-white/5 animate-in fade-in slide-in-from-top-2">
                            <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Output</span>
                            <p className="mt-2 text-blue-100">{transResult}</p>
                        </div>
                    )}
                </div>

                {/* 2. YouTube Card */}
                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl relative group hover:border-red-500/30 transition-all">
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-red-500/0 to-orange-500/0 group-hover:from-red-500/20 group-hover:to-orange-500/20 rounded-3xl opacity-0 group-hover:opacity-100 transition-all blur-md -z-10" />

                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-3 bg-red-500/20 rounded-xl text-red-400">
                            <Youtube size={24} />
                        </div>
                        <h2 className="text-2xl font-semibold">Video Transcript</h2>
                    </div>

                    <div className="space-y-4">
                        <div className="relative">
                            <input
                                type="text"
                                className="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-gray-200 focus:outline-none focus:border-red-500/50 pl-12"
                                placeholder="Paste YouTube URL..."
                                value={ytUrl}
                                onChange={e => setYtUrl(e.target.value)}
                            />
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">
                                <Youtube size={20} />
                            </div>
                        </div>
                        <button
                            onClick={handleYoutube}
                            disabled={ytLoading}
                            className="w-full bg-red-600 hover:bg-red-500 text-white rounded-xl py-3 font-medium transition-colors"
                        >
                            {ytLoading ? "Extracting..." : "Fetch Transcript"}
                        </button>
                    </div>
                    {ytResult && (
                        <div className="mt-6 p-4 bg-black/40 rounded-xl border border-white/5 max-h-[200px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 animate-in fade-in slide-in-from-top-2">
                            <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Transcript</span>
                            <p className="mt-2 text-gray-300 text-sm leading-relaxed">{ytResult}</p>
                        </div>
                    )}
                </div>

                {/* 3. Mind Map Card */}
                <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl relative group hover:border-purple-500/30 transition-all">
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-500/0 to-pink-500/0 group-hover:from-purple-500/20 group-hover:to-pink-500/20 rounded-3xl opacity-0 group-hover:opacity-100 transition-all blur-md -z-10" />

                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-3 bg-purple-500/20 rounded-xl text-purple-400">
                            <Network size={24} />
                        </div>
                        <h2 className="text-2xl font-semibold">Mind Map Generator</h2>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-4 mb-6">
                        <input
                            type="text"
                            className="flex-1 bg-black/40 border border-white/10 rounded-xl p-4 text-gray-200 focus:outline-none focus:border-purple-500/50"
                            placeholder="Topic for mind map (e.g., 'Photosynthesis' or 'Project Plan')"
                            value={mmInput}
                            onChange={e => setMmInput(e.target.value)}
                        />
                        <button
                            onClick={handleMindMap}
                            disabled={mmLoading}
                            className="bg-purple-600 hover:bg-purple-500 text-white px-8 py-4 rounded-xl font-medium transition-colors"
                        >
                            {mmLoading ? "Generating..." : "Generate Map"}
                        </button>
                    </div>

                    <div className="bg-black/40 rounded-xl border border-white/5 min-h-[300px] flex items-center justify-center overflow-hidden relative">
                        {!mmResult && !mmLoading && (
                            <div className="text-center text-gray-600">
                                <Network className="mx-auto mb-2 opacity-50" size={48} />
                                <p>Enter a topic to generate a visualization</p>
                            </div>
                        )}

                        {mmLoading && (
                            <div className="flex gap-2">
                                <div className="w-3 h-3 bg-purple-500 rounded-full animate-bounce" />
                                <div className="w-3 h-3 bg-purple-500 rounded-full animate-bounce delay-100" />
                                <div className="w-3 h-3 bg-purple-500 rounded-full animate-bounce delay-200" />
                            </div>
                        )}

                        <div id="mermaid-test-output" className="w-full h-full p-4 flex items-center justify-center">
                            {/* Mermaid renders here */}
                        </div>
                    </div>
                </div>

            </div>
        </main>
    );
}
