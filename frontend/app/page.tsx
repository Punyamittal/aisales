"use client";

import { useState } from "react";
import { Dashboard } from "@/components/Dashboard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  return (
    <main className="min-h-screen p-6 md:p-10">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white">
          AI Sales
        </h1>
        <p className="mt-1 text-zinc-400">
          Autonomous outreach — GitHub projects → opportunities & revenue
        </p>
      </header>
      <Dashboard apiBase={API_BASE} />
    </main>
  );
}
