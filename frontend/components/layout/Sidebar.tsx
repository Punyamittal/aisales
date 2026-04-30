"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type SidebarProps = {
  isOpen: boolean;
  onClose: () => void;
};

const navItems = [
  { href: "/", label: "Home" },
  { href: "/workflow", label: "Workflow" },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      <aside className="hidden w-64 shrink-0 border-r border-zinc-800 bg-zinc-950/70 p-4 md:block">
        <SidebarContent pathname={pathname} onClose={onClose} />
      </aside>

      {isOpen && (
        <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={onClose}>
          <aside
            className="h-full w-72 border-r border-zinc-800 bg-zinc-950 p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <SidebarContent pathname={pathname} onClose={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}

function SidebarContent({
  pathname,
  onClose,
}: {
  pathname: string;
  onClose: () => void;
}) {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <h2 className="text-sm font-semibold text-zinc-200">Career Workflow</h2>
        <p className="mt-2 text-xs text-zinc-400">
          Build resume, find jobs, optimize ATS score, and launch outreach.
        </p>
      </div>
      <nav className="space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={`block rounded-lg px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-cyan-500/15 text-cyan-300"
                  : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
