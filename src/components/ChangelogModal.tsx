"use client";

import { useState } from "react";
import { X, Sparkles, Calendar, GitCommit } from "lucide-react";
import changelogData from "@/data/changelog.json";

export default function ChangelogModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-[#0A0A0A] border border-white/10 rounded-3xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl shadow-blue-900/20">

                {/* Header */}
                <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/5 rounded-t-3xl">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-xl text-blue-400">
                            <Sparkles size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-white">System Updates</h2>
                            <p className="text-sm text-gray-400">Latest changes and improvements</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                    {changelogData.map((release, idx) => (
                        <div key={idx} className="relative pl-8 border-l border-white/10 last:border-0 pb-2">
                            {/* Timeline Dot */}
                            <div className="absolute left-[-5px] top-0 w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />

                            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2">
                                <h3 className="text-lg font-medium text-white">{release.title} <span className="text-gray-500 text-sm ml-2">v{release.version}</span></h3>
                                <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-white/5 px-2 py-1 rounded-md border border-white/5 self-start sm:self-auto">
                                    <Calendar size={12} />
                                    {release.date}
                                </div>
                            </div>

                            <ul className="space-y-3">
                                {release.changes.map((change, cIdx) => (
                                    <li key={cIdx} className="text-gray-300 text-sm flex items-start gap-3">
                                        <GitCommit size={16} className="text-blue-500/50 mt-0.5 shrink-0" />
                                        <span className="leading-relaxed">{change}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-white/10 bg-black/20 rounded-b-3xl text-center">
                    <p className="text-xs text-gray-500">Updates are deployed automatically to Vercel</p>
                </div>

            </div>
        </div>
    );
}
