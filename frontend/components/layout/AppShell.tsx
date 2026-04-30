"use client";

import { useState } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-zinc-950">
      <Navbar onMenuClick={() => setIsSidebarOpen((prev) => !prev)} />
      <div className="mx-auto flex w-full max-w-7xl">
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />
        <main className="w-full px-4 pb-8 pt-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
