"use client";

import { useState, useMemo } from "react";

type ProjectInput = {
  repo_name: string;
  description: string;
  readme: string;
  tech_stack: string[];
  stars: number;
  forks: number;
};

type CompanyInput = {
  name: string;
  website: string;
  news: string;
  product_info: string;
  funding_info: string;
  job_postings: string;
};

type SuggestedContact = {
  name: string;
  email: string;
  title: string;
  linkedin_url?: string;
};

type SuggestedCompany = {
  company_name: string;
  company_description: string;
  company_domain?: string;
  why_fit: string;
  recommended_roles: string[];
  contacts?: SuggestedContact[];
  personalized_email?: string;
};

type PipelineResult = {
  project_analysis: Record<string, unknown>;
  company_analysis: Record<string, unknown>;
  match: Record<string, unknown>;
  email_body: string;
  deck: { title: string; subtitle: string; slides: { title: string; bullet_points: string[] }[] } | null;
};

export function Dashboard({ apiBase }: { apiBase: string }) {
  const [project, setProject] = useState<ProjectInput>({
    repo_name: "my-app",
    description: "A SaaS dashboard for analytics",
    readme: "## Overview\nBuild dashboards with real-time metrics.",
    tech_stack: ["React", "Node.js", "PostgreSQL"],
    stars: 42,
    forks: 8,
  });
  const [company, setCompany] = useState<CompanyInput>({
    name: "Acme Corp",
    website: "https://acme.example.com",
    news: "Recently raised Series A",
    product_info: "B2B analytics platform",
    funding_info: "Series A, $10M",
    job_postings: "Hiring engineers",
  });
  const [contactRole, setContactRole] = useState("Decision Maker");
  const [includeDeck, setIncludeDeck] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [health, setHealth] = useState<{ status?: string; ollama_model?: string; ollama_reachable?: boolean } | null>(null);
  const [githubQuery, setGithubQuery] = useState("");
  const [githubLoading, setGithubLoading] = useState(false);
  const [githubError, setGithubError] = useState<string | null>(null);
  const [suggestedCompanies, setSuggestedCompanies] = useState<SuggestedCompany[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [suggestEmptyResult, setSuggestEmptyResult] = useState(false);
  const [launchLoading, setLaunchLoading] = useState(false);
  const [launchResult, setLaunchResult] = useState<{ sent: number; failed: number } | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const foundEmails = useMemo(() => {
    const list: { company: string; name: string; title: string; email: string; personalized_email?: string }[] = [];
    suggestedCompanies.forEach((c) => {
      (c.contacts || []).forEach((contact) => {
        if (contact.email) {
          list.push({
            company: c.company_name,
            name: contact.name || contact.email,
            title: contact.title || "",
            email: contact.email,
            personalized_email: c.personalized_email,
          });
        }
      });
    });
    return list;
  }, [suggestedCompanies]);

  const hasEmails = foundEmails.length > 0;

  const checkHealth = async () => {
    try {
      const r = await fetch(`${apiBase}/api/health`);
      const data = await r.json();
      setHealth(data);
    } catch (e) {
      setHealth({ status: "error" });
    }
  };

  const launchEmails = async () => {
    const contacts = foundEmails.map((f) => ({
      email: f.email,
      name: f.name,
      custom_body: f.personalized_email || "",
    }));
    if (contacts.length === 0) {
      setLaunchError("No contact emails found. Run Suggest companies first.");
      return;
    }
    const body =
      result?.email_body ||
      "Hi,\n\nI wanted to reach out to explore a potential partnership. Would you be open to a short call?\n\nBest regards";
    const subject = result?.email_body
      ? "Partnership opportunity"
      : "Quick intro – partnership opportunity";
    setLaunchLoading(true);
    setLaunchError(null);
    setLaunchResult(null);
    try {
      const res = await fetch(`${apiBase}/api/send-outreach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body, contacts }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || res.statusText || "Send failed");
      }
      setLaunchResult({ sent: data.sent ?? 0, failed: data.failed ?? 0 });
    } catch (e) {
      setLaunchError(e instanceof Error ? e.message : "Failed to send emails");
    } finally {
      setLaunchLoading(false);
    }
  };

  const fetchFromGitHub = async () => {
    const q = githubQuery.trim();
    if (!q) return;
    setGithubLoading(true);
    setGithubError(null);
    try {
      const res = await fetch(
        `${apiBase}/api/github/repo?q=${encodeURIComponent(q)}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      setProject({
        repo_name: data.repo_name ?? "",
        description: data.description ?? "",
        readme: data.readme ?? "",
        tech_stack: Array.isArray(data.tech_stack) ? data.tech_stack : [],
        stars: Number(data.stars) || 0,
        forks: Number(data.forks) || 0,
      });
      setGithubQuery("");
    } catch (e) {
      setGithubError(e instanceof Error ? e.message : "Fetch failed");
    } finally {
      setGithubLoading(false);
    }
  };

  const suggestCompanies = async () => {
    setSuggestLoading(true);
    setSuggestError(null);
    setSuggestEmptyResult(false);
    setSuggestedCompanies([]);
    try {
      const res = await fetch(`${apiBase}/api/suggest-companies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = typeof err.detail === "string" ? err.detail : Array.isArray(err.detail) ? err.detail[0]?.msg : null;
        throw new Error(msg || res.statusText);
      }
      const data = await res.json();
      const list = data.companies || [];
      setSuggestedCompanies(list);
      if (list.length === 0) setSuggestEmptyResult(true);
    } catch (e) {
      setSuggestError(e instanceof Error ? e.message : "Suggest failed");
    } finally {
      setSuggestLoading(false);
    }
  };

  const useSuggestedCompany = (c: SuggestedCompany) => {
    setCompany((prev) => ({
      ...prev,
      name: c.company_name,
      product_info: c.company_description,
    }));
    if (c.recommended_roles?.length) setContactRole(c.recommended_roles[0]);
  };

  const runPipeline = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${apiBase}/api/pipeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project,
          company,
          contact_role: contactRole,
          include_deck: includeDeck,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="card p-4 flex items-center justify-between gap-4">
        <span className="text-zinc-400">Backend</span>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={checkHealth}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-700"
          >
            Check health
          </button>
          {health && (
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span
                className={
                  health.status === "ok"
                    ? "text-emerald-400"
                    : "text-amber-500"
                }
              >
                {health.status === "ok" ? "Connected" : "Unreachable"}
              </span>
              {"ollama_reachable" in health && (
                <span className={health.ollama_reachable ? "text-emerald-400" : "text-amber-500"}>
                  Ollama: {health.ollama_reachable ? `OK (${health.ollama_model || "default"})` : "Not running"}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="card p-5">
        <h2 className="text-sm font-medium text-zinc-400 mb-2">
          Fetch project from GitHub
        </h2>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            placeholder="owner/repo or https://github.com/owner/repo"
            value={githubQuery}
            onChange={(e) => {
              setGithubQuery(e.target.value);
              setGithubError(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && fetchFromGitHub()}
            className="flex-1 min-w-[200px] rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500"
          />
          <button
            type="button"
            onClick={fetchFromGitHub}
            disabled={githubLoading || !githubQuery.trim()}
            className="rounded-md bg-zinc-700 px-4 py-2 text-sm text-white hover:bg-zinc-600 disabled:opacity-50"
          >
            {githubLoading ? "Fetching…" : "Fetch"}
          </button>
        </div>
        {githubError && (
          <p className="mt-2 text-sm text-amber-400">{githubError}</p>
        )}
      </div>

      <div className="card p-5">
        <h2 className="text-lg font-semibold text-white mb-2">
          Suggested companies & contacts
        </h2>
        <p className="text-sm text-zinc-400 mb-3">
          Generate a list of companies to contact and which roles to email (e.g. CTO, VP Engineering).
        </p>
        <button
          type="button"
          onClick={suggestCompanies}
          disabled={suggestLoading || !project.repo_name.trim()}
          className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {suggestLoading ? "Generating list…" : "Suggest companies"}
        </button>
        {suggestError && (
          <p className="mt-2 text-sm text-amber-400">{suggestError}</p>
        )}
        {suggestEmptyResult && (
          <p className="mt-2 text-sm text-amber-400">
            No companies were suggested. Ensure Ollama is running and the model can return JSON, then try again.
          </p>
        )}
        {hasEmails && (
          <div className="mt-4 card p-4 bg-zinc-900/80 border-cyan-500/30">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 className="text-base font-semibold text-white">
                Launch emails
              </h3>
              <button
                type="button"
                onClick={launchEmails}
                disabled={launchLoading}
                className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {launchLoading ? "Sending…" : "Launch emails"}
              </button>
            </div>

            {launchResult && (
              <p className="text-sm text-emerald-400 mb-2">
                Sent: {launchResult.sent}, failed: {launchResult.failed}
              </p>
            )}
            {launchError && (
              <p className="text-sm text-amber-400 mb-2">{launchError}</p>
            )}

            <div className="overflow-auto max-h-[280px] rounded border border-zinc-700 mt-2">
              <table className="w-full text-sm">
                <thead className="bg-zinc-800 sticky top-0">
                  <tr>
                    <th className="text-left py-2 px-3 text-zinc-400 font-medium">Company</th>
                    <th className="text-left py-2 px-3 text-zinc-400 font-medium">Name</th>
                    <th className="text-left py-2 px-3 text-zinc-400 font-medium">Title</th>
                    <th className="text-left py-2 px-3 text-zinc-400 font-medium">Email</th>
                    <th className="w-16 py-2 px-3 text-zinc-400 font-medium" />
                  </tr>
                </thead>
                <tbody className="text-zinc-300">
                  {foundEmails.map((row, idx) => (
                    <tr key={idx} className="border-t border-zinc-700 hover:bg-zinc-800/50">
                      <td className="py-2 px-3">{row.company}</td>
                      <td className="py-2 px-3">{row.name}</td>
                      <td className="py-2 px-3 text-zinc-400">{row.title}</td>
                      <td className="py-2 px-3">
                        <a href={`mailto:${row.email}`} className="text-cyan-400 hover:underline truncate block max-w-[220px]" title={row.email}>
                          {row.email}
                        </a>
                      </td>
                      <td className="py-2 px-3 text-right">
                        <button
                          type="button"
                          onClick={() => navigator.clipboard.writeText(row.email)}
                          className="text-[10px] px-2 py-1 rounded bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
                        >
                          Copy
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {suggestedCompanies.length > 0 && (
          <div className="mt-4 space-y-4 max-h-[72vh] overflow-auto">
            {suggestedCompanies.map((c, i) => (
              <div
                key={i}
                className="border border-zinc-700 rounded-lg overflow-hidden bg-zinc-900/50"
              >
                <div className="p-4 pb-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-white text-lg">
                      {c.company_name}
                      {(c.contacts?.length ?? 0) > 0 && (
                        <span className="ml-2 text-xs font-normal text-cyan-400">
                          — {(c.contacts?.length ?? 0)} email{(c.contacts?.length ?? 0) === 1 ? "" : "s"}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => useSuggestedCompany(c)}
                      className="rounded-md bg-zinc-700 px-3 py-1.5 text-sm text-white hover:bg-zinc-600 shrink-0"
                    >
                      Use this company
                    </button>
                  </div>
                  {c.company_description && (
                    <p className="text-sm text-zinc-400 mt-1">
                      {c.company_description}
                    </p>
                  )}
                  {c.why_fit && (
                    <p className="text-sm text-cyan-400/90 mt-1">
                      Why fit: {c.why_fit}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {(c.recommended_roles || []).map((role) => (
                      <span
                        key={role}
                        className="text-xs px-2 py-0.5 rounded bg-zinc-700 text-zinc-300"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                  {c.personalized_email && (
                    <div className="mt-3 p-3 bg-zinc-800/60 rounded border border-zinc-700/50">
                      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1 font-bold">Personalized Pitch</div>
                      <p className="text-xs text-zinc-300 whitespace-pre-wrap italic line-clamp-4 hover:line-clamp-none transition-all cursor-pointer">
                        {c.personalized_email}
                      </p>
                    </div>
                  )}
                </div>
                <div className="px-4 pb-4 pt-2 border-t border-zinc-700 bg-zinc-800/40">
                  <div className="text-xs font-medium text-zinc-400 mb-2">
                    Emails at {c.company_name}
                  </div>
                  {(c.contacts?.length ?? 0) > 0 ? (
                    <ul className="space-y-2">
                      {c.contacts!.map((contact, j) => (
                        <li
                          key={j}
                          className="flex flex-wrap items-center gap-2 text-sm py-1.5 px-2 rounded bg-zinc-900/60 border border-zinc-700/80"
                        >
                          <span className="text-zinc-300 shrink-0">
                            {contact.name || contact.email || "—"}
                            {contact.title && (
                              <span className="text-zinc-500 ml-1">
                                · {contact.title}
                              </span>
                            )}
                          </span>
                          {contact.email ? (
                            <>
                              <a
                                href={`mailto:${contact.email}`}
                                className="text-cyan-400 hover:underline truncate min-w-0 max-w-[240px]"
                                title={contact.email}
                              >
                                {contact.email}
                              </a>
                              <button
                                type="button"
                                onClick={() => {
                                  navigator.clipboard.writeText(contact.email);
                                }}
                                className="text-xs px-2 py-1 rounded bg-zinc-700 text-zinc-300 hover:bg-zinc-600 shrink-0"
                              >
                                Copy
                              </button>
                            </>
                          ) : (
                            <span className="text-zinc-500 italic">No email</span>
                          )}
                          {contact.linkedin_url && (
                            <a
                              href={contact.linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs px-2 py-1 rounded bg-[#0a66c2]/20 text-[#0a66c2] hover:bg-[#0a66c2]/30 shrink-0"
                            >
                              LinkedIn
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-zinc-500 italic">
                      No emails found. We scrape the company site and use Hunter if configured; many sites use contact forms or hide addresses.
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="max-w-2xl">
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-white mb-3">
            Project (GitHub)
          </h2>
          <div className="space-y-3 text-sm">
            <input
              type="text"
              placeholder="Repo name"
              value={project.repo_name}
              onChange={(e) =>
                setProject((p) => ({ ...p, repo_name: e.target.value }))
              }
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-white placeholder-zinc-500"
            />
            <textarea
              placeholder="Description"
              value={project.description}
              onChange={(e) =>
                setProject((p) => ({ ...p, description: e.target.value }))
              }
              rows={2}
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-white placeholder-zinc-500"
            />
            <textarea
              placeholder="README excerpt"
              value={project.readme}
              onChange={(e) =>
                setProject((p) => ({ ...p, readme: e.target.value }))
              }
              rows={3}
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-white placeholder-zinc-500"
            />
            <input
              type="text"
              placeholder="Tech stack (comma-separated)"
              value={(project.tech_stack || []).join(", ")}
              onChange={(e) =>
                setProject((p) => ({
                  ...p,
                  tech_stack: e.target.value.split(",").map((s) => s.trim()),
                }))
              }
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-white placeholder-zinc-500"
            />
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <span className="text-zinc-400">Stars</span>
                <input
                  type="number"
                  min={0}
                  value={project.stars}
                  onChange={(e) =>
                    setProject((p) => ({
                      ...p,
                      stars: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-20 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-white"
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="text-zinc-400">Forks</span>
                <input
                  type="number"
                  min={0}
                  value={project.forks}
                  onChange={(e) =>
                    setProject((p) => ({
                      ...p,
                      forks: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-20 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-white"
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="card p-5 flex flex-wrap items-center gap-4">
        <input
          type="text"
          placeholder="Contact role"
          value={contactRole}
          onChange={(e) => setContactRole(e.target.value)}
          className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-white w-48"
        />
        <label className="flex items-center gap-2 text-zinc-300">
          <input
            type="checkbox"
            checked={includeDeck}
            onChange={(e) => setIncludeDeck(e.target.checked)}
            className="rounded border-zinc-600"
          />
          Include pitch deck
        </label>
        <button
          type="button"
          onClick={runPipeline}
          disabled={loading}
          className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {loading ? "Running pipeline…" : "Run pipeline"}
        </button>
      </div>

      {error && (
        <div className="card p-4 border-amber-500/50 bg-amber-500/10 text-amber-200">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-white">Results</h2>

          <div className="card p-5">
            <h3 className="text-sm font-medium text-zinc-400 mb-2">
              Match (fit score)
            </h3>
            <pre className="text-sm text-zinc-300 overflow-auto max-h-40">
              {JSON.stringify(result.match, null, 2)}
            </pre>
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-medium text-zinc-400 mb-2">
              Generated email body
            </h3>
            <div className="whitespace-pre-wrap text-zinc-300 text-sm rounded bg-zinc-900 p-4 border border-zinc-800">
              {result.email_body}
            </div>
          </div>

          {result.deck && result.deck.slides?.length > 0 && (
            <div className="card p-5">
              <h3 className="text-sm font-medium text-zinc-400 mb-2">
                Pitch deck: {result.deck.title}
              </h3>
              {result.deck.subtitle && (
                <p className="text-zinc-500 text-sm mb-4">
                  {result.deck.subtitle}
                </p>
              )}
              <ul className="space-y-4">
                {result.deck.slides.map((slide, i) => (
                  <li
                    key={i}
                    className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/50"
                  >
                    <div className="font-medium text-cyan-400/90 mb-2">
                      {slide.title}
                    </div>
                    <ul className="list-disc list-inside text-zinc-400 text-sm space-y-1">
                      {slide.bullet_points?.map((b, j) => (
                        <li key={j}>{b}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details className="card p-5">
            <summary className="text-sm font-medium text-zinc-400 cursor-pointer">
              Full JSON (project + company analysis)
            </summary>
            <pre className="mt-3 text-xs text-zinc-500 overflow-auto max-h-60">
              {JSON.stringify(
                {
                  project_analysis: result.project_analysis,
                  company_analysis: result.company_analysis,
                },
                null,
                2
              )}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
