"use client";

import { Copy, Terminal, Check } from "lucide-react";
import { useState } from "react";

export default function DocsPage() {
    return (
        <main className="min-h-screen pt-24 pb-12 px-4 sm:px-8 relative overflow-hidden">
            {/* Background Decor */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px] -z-10" />
            <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-600/10 rounded-full blur-[120px] -z-10" />

            <div className="max-w-5xl mx-auto space-y-12">

                {/* Header */}
                <div className="text-center space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <h1 className="text-4xl sm:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                        API Documentation
                    </h1>
                    <p className="text-gray-400 text-lg max-w-2xl mx-auto">
                        Simple, powerful, and free access to advanced AI models. Integrate seamlessly into your applications.
                    </p>
                </div>

                {/* Endpoint Section */}
                <div className="glass-panel p-8 rounded-2xl border border-white/10 space-y-4 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
                    <div className="flex items-center gap-3 mb-2">
                        <Terminal className="text-blue-400" />
                        <h2 className="text-xl font-semibold text-white">Endpoint</h2>
                    </div>
                    <div className="flex items-center gap-4 bg-black/40 p-4 rounded-xl border border-white/5 font-mono text-sm sm:text-base text-gray-300">
                        <span className="text-green-400 font-bold">POST</span>
                        <span className="break-all">/api/chat</span>
                        <span className="ml-auto text-xs text-gray-500 hidden sm:block">JSON</span>
                    </div>
                    <p className="text-gray-400 text-sm">
                        Send a POST request to this endpoint with a JSON body containing your messages and model selection.
                    </p>
                </div>

                {/* Request Examples */}
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
                    <h2 className="text-2xl font-bold text-white px-2">Request Examples</h2>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <CodeBlock
                            language="BASH / cURL"
                            code={`curl -X POST https://your-domain.com/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": false
  }'`}
                        />

                        <CodeBlock
                            language="JavaScript / Node.js"
                            code={`const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'gpt-3.5-turbo',
    messages: [
      { role: 'user', content: 'Hello!' }
    ]
  })
});

const data = await response.json();
console.log(data);`}
                        />

                        <CodeBlock
                            language="Python"
                            code={`import requests

url = "https://your-domain.com/api/chat"
payload = {
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ]
}

response = requests.post(url, json=payload)
print(response.json())`}
                        />

                        <div className="glass-panel p-6 rounded-2xl border border-white/10">
                            <h3 className="text-lg font-semibold text-white mb-4">Supported Models</h3>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                                    <span className="text-white font-mono">gpt-3.5-turbo</span> (Default)
                                </li>
                                <li className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                                    <span className="text-white font-mono">gpt-4</span>
                                </li>
                                <li className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                                    <span className="text-white font-mono">claude-3-opus</span>
                                </li>
                                <li className="pt-2 text-xs italic opacity-60">* Availability depends on the backend provider pool.</li>
                            </ul>
                        </div>
                    </div>
                </div>

            </div>
        </main>
    );
}

function CodeBlock({ language, code }: { language: string, code: string }) {
    const [copied, setCopied] = useState(false);

    const copyToClipboard = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="glass-panel rounded-2xl border border-white/10 overflow-hidden flex flex-col h-full">
            <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/5">
                <span className="text-sm font-medium text-gray-300">{language}</span>
                <button
                    onClick={copyToClipboard}
                    className="text-gray-400 hover:text-white transition-colors"
                    title="Copy code"
                >
                    {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} />}
                </button>
            </div>
            <div className="p-4 bg-black/40 overflow-x-auto flex-1">
                <pre className="font-mono text-sm text-blue-100 whitespace-pre">
                    {code}
                </pre>
            </div>
        </div>
    );
}
