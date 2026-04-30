"use client";

import { useState } from "react";
import { apiGet, axiosExample } from "@/lib/api";

type ApiIntegrationPlaceholderProps = {
  endpoint: string;
};

export function ApiIntegrationPlaceholder({
  endpoint,
}: ApiIntegrationPlaceholderProps) {
  const [message, setMessage] = useState("Ready to connect API");

  const testFetch = async () => {
    try {
      const data = await apiGet(endpoint);
      setMessage(`Fetch connected: ${JSON.stringify(data).slice(0, 80)}...`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `Fetch placeholder error: ${error.message}`
          : "Fetch placeholder failed"
      );
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <h3 className="text-sm font-semibold text-zinc-100">API Integration Stub</h3>
      <p className="mt-1 text-xs text-zinc-400">
        Endpoint: <span className="text-cyan-300">{endpoint}</span>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={testFetch}
          className="rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-500"
        >
          Test with fetch
        </button>
        <button
          type="button"
          onClick={() => setMessage(axiosExample(endpoint))}
          className="rounded-md bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-600"
        >
          Show axios example
        </button>
      </div>
      <p className="mt-3 text-xs text-zinc-300">{message}</p>
    </div>
  );
}
