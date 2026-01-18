"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Sparkles, Zap, Shield, History } from "lucide-react";
import ChangelogModal from "@/components/ChangelogModal";

export default function Home() {
  const [showChangelog, setShowChangelog] = useState(false);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-24 relative overflow-hidden">
      {/* Background Decor - animated blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-[120px] -z-10 animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-[120px] -z-10 animate-pulse delay-1000" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-white/5 rounded-full blur-[100px] -z-20" />

      <div className="max-w-4xl w-full text-center space-y-12 z-10">

        {/* Header Section */}
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-white/10 text-sm font-medium text-blue-200 mb-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <Sparkles size={16} className="text-blue-400" />
            <span>Next-Generation API Platform</span>
          </div>

          <h1 className="text-5xl sm:text-7xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-blue-100 to-white/50 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
            Unleash the Power of <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">ChatGPT 5 & AI Tools</span>
          </h1>

          <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
            Access state-of-the-art language models including ChatGPT 5.
            Use our new Translator and YouTube Caption APIs today.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center animate-in fade-in slide-in-from-bottom-12 duration-700 delay-300">
          <Link href="/login" className="group">
            <button className="relative px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl font-bold text-white shadow-lg shadow-blue-900/20 hover:shadow-blue-600/40 transition-all duration-300 hover:scale-105 active:scale-95 flex items-center gap-3 overflow-hidden">
              <span className="relative z-10">Get Started with GPT-5</span>
              <ArrowRight size={20} className="relative z-10 group-hover:translate-x-1 transition-transform" />
              {/* Button shine effect */}
              <div className="absolute top-0 -left-full w-full h-full bg-linear-to-r from-transparent via-white/20 to-transparent skew-x-12 group-hover:animate-shine" />
            </button>
          </Link>

          <Link href="https://github.com/gpt4free-ts/gpt4free-ts" target="_blank" className="group">
            <button className="px-8 py-4 glass rounded-2xl font-semibold text-gray-300 hover:text-white border border-white/10 hover:border-white/30 transition-all duration-300 hover:bg-white/5">
              View Documentation
            </button>
          </Link>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-12 text-left animate-in fade-in slide-in-from-bottom-16 duration-700 delay-500">
          <FeatureCard
            icon={<Zap className="text-yellow-400" />}
            title="Lightning Fast"
            desc="Optimized for low-latency responses using edge deployment."
          />
          <FeatureCard
            icon={<Shield className="text-green-400" />}
            title="Secure Access"
            desc="Enterprise-grade security with encrypted tokens."
          />
          <FeatureCard
            icon={<Sparkles className="text-purple-400" />}
            title="Premium Models"
            desc="Access to top-tier LLMs including ChatGPT 5 and Claude 3."
          />
        </div>

      </div>

      <div className="absolute bottom-6 flex items-center gap-6 text-xs text-gray-600">
        <span>© 2024 AI API Platform. All rights reserved.</span>
        <button
          onClick={() => setShowChangelog(true)}
          className="flex items-center gap-1 hover:text-blue-400 transition-colors"
        >
          <History size={12} />
          Updates & Changelog
        </button>
      </div>

      <ChangelogModal isOpen={showChangelog} onClose={() => setShowChangelog(false)} />
    </main>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="glass-panel p-6 rounded-2xl border border-white/10 hover:border-blue-500/30 transition-all duration-300 hover:-translate-y-1">
      <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center mb-4 border border-white/10">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
    </div>
  )
}
