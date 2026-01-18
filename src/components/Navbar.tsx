"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, LogIn, Github, Book, MessageSquare } from "lucide-react";

export default function Navbar() {
    const pathname = usePathname();

    const isActive = (path: string) => pathname === path;

    return (
        <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-xl">
            <div className="glass-panel rounded-full px-6 py-3 flex items-center justify-between shadow-2xl border border-white/10 bg-black/40 backdrop-blur-xl">
                <Link
                    href="/"
                    className={`p-2 rounded-full transition-all duration-300 hover:bg-white/10 ${isActive('/') ? 'text-blue-400 bg-white/5' : 'text-gray-400 hover:text-white'}`}
                    title="Home"
                >
                    <Home size={20} />
                </Link>

                <div className="w-px h-4 bg-white/10" />

                <Link
                    href="/dashboard"
                    className={`p-2 rounded-full transition-all duration-300 hover:bg-white/10 ${isActive('/dashboard') ? 'text-blue-400 bg-white/5' : 'text-gray-400 hover:text-white'}`}
                    title="Dashboard"
                >
                    <LayoutDashboard size={20} />
                </Link>

                <div className="w-px h-4 bg-white/10" />

                <Link
                    href="/docs"
                    className={`p-2 rounded-full transition-all duration-300 hover:bg-white/10 ${isActive('/docs') ? 'text-blue-400 bg-white/5' : 'text-gray-400 hover:text-white'}`}
                    title="API Documentation"
                >
                    <Book size={20} />
                </Link>

                <div className="w-px h-4 bg-white/10" />

                <Link
                    href="/playground"
                    className={`p-2 rounded-full transition-all duration-300 hover:bg-white/10 ${isActive('/playground') ? 'text-blue-400 bg-white/5' : 'text-gray-400 hover:text-white'}`}
                    title="Interactive Playground"
                >
                    <MessageSquare size={20} />
                </Link>

                <div className="w-px h-4 bg-white/10" />

                <Link
                    href="/login"
                    className={`p-2 rounded-full transition-all duration-300 hover:bg-white/10 ${isActive('/login') ? 'text-blue-400 bg-white/5' : 'text-gray-400 hover:text-white'}`}
                    title="Login"
                >
                    <LogIn size={20} />
                </Link>

                <div className="w-px h-4 bg-white/10" />

                <a
                    href="https://github.com/gpt4free-ts/gpt4free-ts"
                    target="_blank"
                    className="p-2 rounded-full transition-all duration-300 hover:bg-white/10 text-gray-400 hover:text-white"
                    title="Source Code"
                >
                    <Github size={20} />
                </a>
            </div>
        </nav>
    );
}
