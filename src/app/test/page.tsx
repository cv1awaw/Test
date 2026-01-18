"use client";

import { useState, useEffect } from "react";
import {
    Send, Globe, Youtube, MessageSquare, Network, Sparkles,
    CheckCircle, AlertCircle, Loader2, PlayCircle, Mic
} from "lucide-react";
import mermaid from "mermaid";

export default function TestPage() {
    // --- State ---
    const [activeTab, setActiveTab] = useState<'translate' | 'youtube' | 'mindmap'>('translate');

    // Translator
    const [transText, setTransText] = useState("");
    const [transTarget, setTransTarget] = useState("es");
    const [transResult, setTransResult] = useState("");
    const [transLoading, setTransLoading] = useState(false);

    // YouTube
    const [ytUrl, setYtUrl] = useState("");
    const [ytResult, setYtResult] = useState("");
    const [ytLoading, setYtLoading] = useState(false);

    // Mind Map
    const [mmInput, setMmInput] = useState("");
    const [mmResult, setMmResult] = useState("");
    const [mmLoading, setMmLoading] = useState(false);

    // --- Effects ---
    useEffect(() => {
        mermaid.initialize({
            startOnLoad: true,
            theme: 'dark',
            securityLevel: 'loose',
            fontFamily: 'sans-serif'
        });
    }, []);

    useEffect(() => {
        if (mmResult && (mmResult.startsWith('graph') || mmResult.startsWith('mindmap'))) {
            const renderMap = async () => {
                try {
                    const element = document.getElementById("mermaid-output");
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
    }, [mmResult, activeTab]);

    // --- Handlers ---
    const handleTranslate = async () => {
        if (!transText.trim()) return;
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
        if (!ytUrl.trim()) return;
        setYtLoading(true);
        try {
            const res = await fetch("/api/transcript", {
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
        if (!mmInput.trim()) return;
        setMmLoading(true);
        setMmResult("");
        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: "gpt-5", // Or gpt-4o as needed
                    messages: [
                        { role: "system", content: "You are a Mind Map Generator. Output ONLY valid Mermaid.js syntax. Start immediately with `mindmap` or `graph TD`. Do not use code blocks." },
                        { role: "user", content: `Create a comprehensive mind map about: ${mmInput}` }
                    ],
                    stream: false
                })
            });
            const data = await res.json();
            let content = data.choices?.[0]?.message?.content || "";
            // Cleanup common LLM artifacts
            content = content.replace(/```mermaid/g, "").replace(/```/g, "").trim();
            setMmResult(content);
        } catch (e: any) {
            setMmResult("Error: " + e.message);
        }
        setMmLoading(false);
    };

    return (
        <main className="min-h-screen bg-black text-white p-6 sm:p-12 relative overflow-hidden pt-24">
            {/* Ambient Background */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[128px] -z-10 animate-pulse" />
            <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-600/10 rounded-full blur-[128px] -z-10 animate-pulse delay-700" />

            <div className="max-w-5xl mx-auto space-y-8">

                {/* Header */}
                <div className="text-center space-y-4 mb-12 animate-in fade-in slide-in-from-top-4 duration-700">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20">
                        <Sparkles size={12} />
                        <span>Experimental Features</span>
                    </div>
                    <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
                        AI <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">Laboratory</span>
                    </h1>
                    <p className="text-gray-400 max-w-2xl mx-auto">
                        Test and interact with our latest neural modules.
                    </p>
                </div>

                {/* Tabs Navigation */}
                <div className="flex justify-center mb-8">
                    <div className="bg-white/5 backdrop-blur-md p-1 rounded-2xl border border-white/10 flex flex-wrap justify-center gap-1">
                        <TabButton
                            active={activeTab === 'translate'}
                            onClick={() => setActiveTab('translate')}
                            icon={<Globe size={18} />}
                            label="Neural Translate"
                        />
                        <TabButton
                            active={activeTab === 'youtube'}
                            onClick={() => setActiveTab('youtube')}
                            icon={<Youtube size={18} />}
                            label="Video Intelligence"
                        />
                        <TabButton
                            active={activeTab === 'mindmap'}
                            onClick={() => setActiveTab('mindmap')}
                            icon={<Network size={18} />}
                            label="Structure Viz"
                        />
                    </div>
                </div>

                {/* Content Area */}
                <div className="min-h-[400px]">

                    {/* TRANSLATOR */}
                    {activeTab === 'translate' && (
                        <div className="max-w-3xl mx-auto animate-in fade-in zoom-in-95 duration-300">
                            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 space-y-6">
                                <div className="space-y-4">
                                    <label className="text-sm font-medium text-gray-400 ml-1">Input Text</label>
                                    <textarea
                                        className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 text-gray-200 focus:outline-none focus:border-blue-500/50 min-h-[140px] resize-none transition-all"
                                        placeholder="Enter text to translate..."
                                        value={transText}
                                        onChange={e => setTransText(e.target.value)}
                                    />
                                </div>

                                <div className="flex flex-col sm:flex-row gap-4">
                                    <select
                                        className="bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-gray-300 focus:outline-none hover:bg-white/5 transition-colors cursor-pointer"
                                        value={transTarget}
                                        onChange={e => setTransTarget(e.target.value)}
                                    >
                                        <option value="es">Spanish (Español)</option>
                                        <option value="fr">French (Français)</option>
                                        <option value="de">German (Deutsch)</option>
                                        <option value="ja">Japanese (日本語)</option>
                                        <option value="zh">Chinese (中文)</option>
                                        <option value="ru">Russian (Русский)</option>
                                    </select>

                                    <button
                                        onClick={handleTranslate}
                                        disabled={transLoading || !transText.trim()}
                                        className="flex-1 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 py-3"
                                    >
                                        {transLoading ? <Loader2 className="animate-spin" size={20} /> : <Globe size={20} />}
                                        {transLoading ? "Translating..." : "Translate Now"}
                                    </button>
                                </div>

                                {transResult && (
                                    <div className="mt-6 pt-6 border-t border-white/10 animate-in fade-in slide-in-from-top-2">
                                        <span className="text-xs uppercase tracking-wider text-blue-400 font-bold mb-2 block">Translation Output</span>
                                        <p className="text-lg text-white leading-relaxed">{transResult}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* YOUTUBE */}
                    {activeTab === 'youtube' && (
                        <div className="max-w-3xl mx-auto animate-in fade-in zoom-in-95 duration-300">
                            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 space-y-6 relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-32 bg-red-600/5 rounded-full blur-3xl -z-10" />

                                <div className="space-y-4">
                                    <label className="text-sm font-medium text-gray-400 ml-1">YouTube URL</label>
                                    <div className="relative group">
                                        <input
                                            type="text"
                                            className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 pl-12 text-gray-200 focus:outline-none focus:border-red-500/50 transition-all"
                                            placeholder="https://www.youtube.com/watch?v=..."
                                            value={ytUrl}
                                            onChange={e => setYtUrl(e.target.value)}
                                        />
                                        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-red-500 transition-colors">
                                            <Youtube size={20} />
                                        </div>
                                    </div>
                                </div>

                                <button
                                    onClick={handleYoutube}
                                    disabled={ytLoading || !ytUrl.trim()}
                                    className="w-full bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white rounded-xl py-3 font-medium transition-all shadow-lg shadow-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {ytLoading ? <Loader2 className="animate-spin" size={20} /> : <PlayCircle size={20} />}
                                    {ytLoading ? "Extracting Content..." : "Fetch Transcript"}
                                </button>

                                {ytResult && (
                                    <div className="mt-6 bg-black/40 rounded-2xl border border-white/5 p-4 max-h-[400px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent animate-in fade-in slide-in-from-top-2">
                                        <div className="flex items-center justify-between mb-4 sticky top-0 bg-black/80 backdrop-blur-sm p-2 rounded-lg z-10">
                                            <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Transcript Content</span>
                                            <button
                                                onClick={() => navigator.clipboard.writeText(ytResult)}
                                                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                            >
                                                Copy Text
                                            </button>
                                        </div>
                                        <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{ytResult}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* MIND MAP */}
                    {activeTab === 'mindmap' && (
                        <div className="max-w-4xl mx-auto animate-in fade-in zoom-in-95 duration-300">
                            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 space-y-6">
                                <div className="flex flex-col sm:flex-row gap-4">
                                    <input
                                        type="text"
                                        className="flex-1 bg-black/40 border border-white/10 rounded-2xl p-4 text-gray-200 focus:outline-none focus:border-purple-500/50 transition-all"
                                        placeholder="What would you like to visualize?"
                                        value={mmInput}
                                        onChange={e => setMmInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleMindMap()}
                                    />
                                    <button
                                        onClick={handleMindMap}
                                        disabled={mmLoading || !mmInput.trim()}
                                        className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white px-8 py-4 rounded-2xl font-medium transition-all shadow-lg shadow-purple-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 whitespace-nowrap"
                                    >
                                        {mmLoading ? <Loader2 className="animate-spin" size={20} /> : <Network size={20} />}
                                        {mmLoading ? "Thinking..." : "Generate"}
                                    </button>
                                </div>

                                <div className="bg-black/30 rounded-3xl border border-white/5 min-h-[500px] flex items-center justify-center overflow-hidden relative group">
                                    {!mmResult && !mmLoading && (
                                        <div className="text-center text-gray-600">
                                            <Network className="mx-auto mb-4 opacity-20" size={64} />
                                            <p>Enter a topic above to generate a mind map</p>
                                        </div>
                                    )}

                                    {mmLoading && (
                                        <div className="flex flex-col items-center gap-4">
                                            <Loader2 className="text-purple-500 animate-spin" size={48} />
                                            <p className="text-gray-400 animate-pulse">Analyzing structure...</p>
                                        </div>
                                    )}

                                    <div
                                        id="mermaid-output"
                                        className="w-full h-full p-8 flex items-center justify-center overflow-auto"
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                </div>
            </div>
        </main>
    );
}

function TabButton({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) {
    return (
        <button
            onClick={onClick}
            className={`
                px-6 py-3 rounded-xl font-medium text-sm transition-all duration-300 flex items-center gap-2
                ${active
                    ? 'bg-white/10 text-white shadow-lg shadow-white/5 border border-white/10'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }
            `}
        >
            {icon}
            {label}
        </button>
    )
}
