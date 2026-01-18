"use client";

import { useState } from "react";
import { Send, Globe, Youtube, MessageSquare } from "lucide-react";

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

    // Chat State
    const [chatInput, setChatInput] = useState("");
    const [chatResult, setChatResult] = useState("");
    const [chatLoading, setChatLoading] = useState(false);

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

    const handleChat = async () => {
        setChatLoading(true);
        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: "gpt-5",
                    messages: [{ role: "user", content: chatInput }],
                    stream: false
                })
            });
            const data = await res.json();
            setChatResult(data.choices?.[0]?.message?.content || JSON.stringify(data));
        } catch (e: any) {
            setChatResult("Error: " + e.message);
        }
        setChatLoading(false);
    };

    return (
        <main className="min-h-screen bg-black text-white p-8 space-y-12">
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
                API Test Dashboard
            </h1>

            {/* Translator Section */}
            <section className="space-y-4 p-6 glass-panel border border-white/10 rounded-2xl">
                <div className="flex items-center gap-2 text-xl font-semibold text-blue-300">
                    <Globe /> Translator API
                </div>
                <div className="flex gap-4">
                    <textarea
                        className="flex-1 bg-white/5 rounded-lg p-3 text-white"
                        rows={3}
                        placeholder="Enter text to translate..."
                        value={transText}
                        onChange={e => setTransText(e.target.value)}
                    />
                    <select
                        className="bg-white/10 rounded-lg p-3 text-white"
                        value={transTarget}
                        onChange={e => setTransTarget(e.target.value)}
                    >
                        <option value="es">Spanish</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                        <option value="ja">Japanese</option>
                        <option value="ar">Arabic</option>
                    </select>
                </div>
                <button
                    onClick={handleTranslate}
                    disabled={transLoading}
                    className="bg-blue-600 hover:bg-blue-500 px-6 py-2 rounded-lg font-medium"
                >
                    {transLoading ? "Translating..." : "Translate"}
                </button>
                {transResult && (
                    <div className="bg-green-900/20 border border-green-500/30 p-4 rounded-lg mt-4">
                        <h4 className="text-xs uppercase text-green-400 mb-1">Result:</h4>
                        <p>{transResult}</p>
                    </div>
                )}
            </section>

            {/* YouTube Section */}
            <section className="space-y-4 p-6 glass-panel border border-white/10 rounded-2xl">
                <div className="flex items-center gap-2 text-xl font-semibold text-red-400">
                    <Youtube /> YouTube Captions API
                </div>
                <div className="flex gap-4">
                    <input
                        type="text"
                        className="flex-1 bg-white/5 rounded-lg p-3 text-white"
                        placeholder="YouTube Video URL..."
                        value={ytUrl}
                        onChange={e => setYtUrl(e.target.value)}
                    />
                </div>
                <button
                    onClick={handleYoutube}
                    disabled={ytLoading}
                    className="bg-red-600 hover:bg-red-500 px-6 py-2 rounded-lg font-medium"
                >
                    {ytLoading ? "Fetching..." : "Get Transcript"}
                </button>
                {ytResult && (
                    <div className="bg-green-900/20 border border-green-500/30 p-4 rounded-lg mt-4 max-h-60 overflow-y-auto">
                        <h4 className="text-xs uppercase text-green-400 mb-1">Transcript:</h4>
                        <p className="whitespace-pre-wrap text-sm">{ytResult}</p>
                    </div>
                )}
            </section>

            {/* Chat Section */}
            <section className="space-y-4 p-6 glass-panel border border-white/10 rounded-2xl">
                <div className="flex items-center gap-2 text-xl font-semibold text-purple-400">
                    <MessageSquare /> ChatGPT 5 Test
                </div>
                <div className="flex gap-4">
                    <input
                        type="text"
                        className="flex-1 bg-white/5 rounded-lg p-3 text-white"
                        placeholder="Ask ChatGPT 5..."
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                    />
                </div>
                <button
                    onClick={handleChat}
                    disabled={chatLoading}
                    className="bg-purple-600 hover:bg-purple-500 px-6 py-2 rounded-lg font-medium"
                >
                    {chatLoading ? "Thinking..." : "Send Request (gpt-5)"}
                </button>
                {chatResult && (
                    <div className="bg-green-900/20 border border-green-500/30 p-4 rounded-lg mt-4">
                        <h4 className="text-xs uppercase text-green-400 mb-1">Response:</h4>
                        <p className="whitespace-pre-wrap text-sm">{chatResult}</p>
                    </div>
                )}
            </section>
        </main>
    );
}

function FeatureCard({ icon, title, desc }: { icon: any, title: string, desc: string }) {
    return (
        <div className="p-4 bg-white/5 rounded-xl">
            <div className="flex items-center gap-3 mb-2">
                {icon}
                <div className="font-semibold">{title}</div>
            </div>
            <div className="text-sm text-gray-400">{desc}</div>
        </div>
    )
}
