"use client";

import Link from "next/link";

type NavbarProps = {
  onMenuClick: () => void;
};

export function Navbar({ onMenuClick }: NavbarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/85 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onMenuClick}
            className="inline-flex rounded-md border border-zinc-700 p-2 text-zinc-200 hover:bg-zinc-800 md:hidden"
            aria-label="Toggle navigation"
          >
            <span className="text-sm">Menu</span>
          </button>
          <Link href="/" className="text-lg font-semibold tracking-tight text-white">
            AI Career Assistant
          </Link>
        </div>
        <nav className="hidden items-center gap-2 md:flex">
          <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
            Beta
          </span>
        </nav>
      </div>
    </header>
  );
}
