"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { careerApi, loadLocalState, saveLocalState } from "@/lib/api";

type JobItem = {
  job_id: string;
  title: string;
  company: string;
  location: string;
  match_score: number;
  apply_link: string;
};

type Contact = { name: string; title: string; email: string };
type SavedProfile = {
  profile_id?: string;
  readiness_score?: number;
  normalized_skills?: string[];
};

export default function WorkflowPage() {
  const [role, setRole] = useState("Software Engineer");
  const [company, setCompany] = useState("acme.com");
  const [github, setGithub] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [resumeText, setResumeText] = useState("Built backend services with Python, FastAPI, SQL, Docker.");
  const [status, setStatus] = useState("");
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [resumeSummary, setResumeSummary] = useState("");
  const [pdfPath, setPdfPath] = useState("");
  const [atsScore, setAtsScore] = useState<number | null>(null);
  const [atsSuggestions, setAtsSuggestions] = useState<string[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [emailPreview, setEmailPreview] = useState("");
  const [runningAll, setRunningAll] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [dashboardSnapshot, setDashboardSnapshot] = useState<Record<string, unknown>>({
    input: null,
    profile: null,
    job: null,
    resume: null,
    ats: null,
    outreach: null,
    optimized: null,
    overleaf: null,
  });
  const [optimizedPackage, setOptimizedPackage] = useState<{
    optimized_resume: string;
    key_improvements: string[];
    personalized_outreach_email: string;
    estimated_ats_score: number;
    estimated_match_score: number;
  } | null>(null);
  const [overleafExport, setOverleafExport] = useState<{
    export_id: string;
    overleaf_url: string;
    tex_download_url: string;
    pdf_download_url?: string | null;
    no_real_images_found: boolean;
    warnings: string[];
  } | null>(null);
  const [showDebugSnapshot, setShowDebugSnapshot] = useState(false);

  useEffect(() => {
    setMounted(true);
    refreshDashboardSnapshot();
  }, []);

  function refreshDashboardSnapshot() {
    setDashboardSnapshot({
      input: loadLocalState("career.input"),
      profile: loadLocalState("career.profile"),
      job: loadLocalState("career.job"),
      resume: loadLocalState("career.resume"),
      ats: loadLocalState("career.ats"),
      outreach: loadLocalState("career.outreach"),
      optimized: loadLocalState("career.optimized"),
      overleaf: loadLocalState("career.overleaf"),
    });
  }

  async function saveProfile() {
    // Clear downstream artifacts so stale data does not survive new profile input.
    saveLocalState("career.job", null);
    saveLocalState("career.resume", null);
    saveLocalState("career.ats", null);
    saveLocalState("career.outreach", null);
    setJobs([]);
    setResumeSummary("");
    setPdfPath("");
    setAtsScore(null);
    setAtsSuggestions([]);
    setContacts([]);
    setEmailPreview("");

    saveLocalState("career.input", { role, company, github, linkedin, resumeText });
    refreshDashboardSnapshot();
    try {
      setStatus("Saving profile...");
      const profile = await careerApi.ingestProfile({
        user_id: "local-user",
        source: { github_url: github, linkedin_url: linkedin },
        raw_resume_text: resumeText,
        preferences: {
          target_roles: [role],
          locations: ["Remote"],
          employment_type: ["Full-time"],
          visa_required: false,
        },
      });
      saveLocalState("career.profile", profile);
      refreshDashboardSnapshot();
      setStatus(`Profile saved: ${profile.profile_id}`);
      return profile;
    } catch (error) {
      // Keep workflow moving even if backend is temporarily down.
      const fallback = { profile_id: `local-${Date.now()}` };
      saveLocalState("career.profile", fallback);
      refreshDashboardSnapshot();
      setStatus(
        error instanceof Error
          ? `Saved locally only (API failed): ${error.message}`
          : "Saved locally only (API failed)."
      );
      return fallback;
    }
  }

  async function fetchJobs() {
    const profile = loadLocalState<{ profile_id: string }>("career.profile");
    if (!profile?.profile_id) {
      setStatus("Save profile first.");
      return [];
    }
    setStatus("Fetching jobs...");
    const result = await careerApi.searchJobs(profile.profile_id, company, "Remote");
    const list = result.items || [];
    setJobs(list);
    if (list.length > 0) {
      saveLocalState("career.job", list[0]);
    }
    refreshDashboardSnapshot();
    setStatus(`Found ${list.length} jobs.`);
    return list;
  }

  async function generateResume() {
    const profile = loadLocalState<{ profile_id: string }>("career.profile");
    const job = loadLocalState<{ job_id: string }>("career.job");
    if (!profile?.profile_id || !job?.job_id) {
      setStatus("Need profile and selected job.");
      return;
    }
    setStatus("Generating LaTeX resume (Gemma 4 + Overleaf)...");
    try {
      const result = await careerApi.generateOverleafResume({
        profile_id: profile.profile_id,
        job_id: job.job_id,
        candidate_name: "Punya Mittal",
      });
      const resumeRecord = {
        resume_id: result.export_id,
        summary: "LaTeX resume generated via Gemma 4 and Overleaf export.",
        storage_path: result.pdf_download_url || "",
        pdf_path: result.pdf_download_url || "",
      };
      saveLocalState("career.resume", resumeRecord);
      setOverleafExport(result);
      saveLocalState("career.overleaf", result);
      refreshDashboardSnapshot();
      setResumeSummary(resumeRecord.summary);
      setPdfPath(result.pdf_download_url || "");
      setStatus("LaTeX resume generated.");
      return resumeRecord;
    } catch (error) {
      setStatus(
        error instanceof Error
          ? `LaTeX resume generation failed: ${error.message}`
          : "LaTeX resume generation failed."
      );
      return null;
    }
  }

  async function analyzeAts() {
    const resume = loadLocalState<{ resume_id: string }>("career.resume");
    const job = loadLocalState<{ job_id: string }>("career.job");
    if (!resume?.resume_id || !job?.job_id) {
      setStatus("Generate resume first.");
      return;
    }
    setStatus("Analyzing ATS...");
    try {
      const result = await careerApi.analyzeAts({
        resume_id: resume.resume_id,
        job_id: job.job_id,
        ruleset: "default_v1",
      });
      saveLocalState("career.ats", result);
      refreshDashboardSnapshot();
      setAtsScore(result.ats_score ?? null);
      setAtsSuggestions(result.suggestions || []);
      setStatus("ATS analysis complete.");
      return result;
    } catch (error) {
      const fallback = {
        ats_score: 72,
        suggestions: [
          "Add more role-specific keywords from job description.",
          "Quantify project impact with metrics.",
          "Highlight internship outcomes in bullets.",
        ],
      };
      saveLocalState("career.ats", fallback);
      refreshDashboardSnapshot();
      setAtsScore(fallback.ats_score);
      setAtsSuggestions(fallback.suggestions);
      setStatus(
        error instanceof Error
          ? `ATS API failed, local fallback used: ${error.message}`
          : "ATS API failed, local fallback used."
      );
      return fallback;
    }
  }

  async function generateOutreach() {
    const profile = loadLocalState<{ profile_id: string }>("career.profile");
    const job = loadLocalState<{ job_id: string; company: string }>("career.job");
    const resume = loadLocalState<{ resume_id: string }>("career.resume");
    if (!profile?.profile_id || !job?.job_id || !resume?.resume_id) {
      setStatus("Complete profile, job, and resume first.");
      return;
    }
    setStatus("Finding employees and generating emails...");
    try {
      const found = await careerApi.findEmployees(company, job.job_id);
      const selected = (found.contacts || []).slice(0, 3);
      setContacts(selected);
      const noRealEmailsFound = !!found.no_real_emails_found;
      if (noRealEmailsFound) {
        setStatus(`No real emails found via ${found.scraper_source || "scraper"}; generated message only.`);
      }
      if (!selected.length) {
        throw new Error("No employees returned by API");
      }
      const draft = await careerApi.generateEmails({
        profile_id: profile.profile_id,
        job_id: job.job_id,
        resume_id: resume.resume_id,
        recipient: {
          name: selected[0].name,
          role: selected[0].title,
          company: job.company || company,
          email: selected[0].email,
        },
        variant: "intro",
      });
      saveLocalState("career.outreach", { contacts: selected, draft });
      refreshDashboardSnapshot();
      setEmailPreview(draft.body || "");
      setStatus("Outreach generated.");
      return { contacts: selected, draft };
    } catch (error) {
      const fallbackContacts = [{ name: "Hiring Manager", title: "AI Team", email: "" }];
      const fallbackDraft = {
        body: `Hi Hiring Manager,\n\nI am interested in AI Intern opportunities at ${company}. I have hands-on ML/backend experience and would value a referral or quick guidance.\n\nThanks,\nPunya Mittal`,
      };
      setContacts(fallbackContacts);
      setEmailPreview(fallbackDraft.body);
      saveLocalState("career.outreach", { contacts: fallbackContacts, draft: fallbackDraft });
      refreshDashboardSnapshot();
      setStatus(
        error instanceof Error
          ? `Outreach API failed, local fallback used: ${error.message}`
          : "Outreach API failed, local fallback used."
      );
      return { contacts: fallbackContacts, draft: fallbackDraft };
    }
  }

  async function runFullWorkflow() {
    try {
      setRunningAll(true);
      setStatus("Running full workflow...");

      const profile = await saveProfile();
      if (!profile?.profile_id) {
        setStatus("Profile step failed.");
        return;
      }

      const fetchedJobs = await fetchJobs();
      if (!fetchedJobs.length) {
        setStatus("No jobs found. Workflow stopped.");
        return;
      }

      await generateResume();
      await analyzeAts();
      await generateOutreach();
      await optimizeApplicationPackage();
      setStatus("Full workflow completed (with API/local fallbacks as needed).");
    } catch (error) {
      setStatus(error instanceof Error ? `Workflow failed: ${error.message}` : "Workflow failed.");
    } finally {
      setRunningAll(false);
    }
  }

  async function optimizeApplicationPackage() {
    const profile = loadLocalState<{ profile_id: string }>("career.profile");
    const job = loadLocalState<{ job_id: string }>("career.job");
    if (!profile?.profile_id || !job?.job_id) {
      setStatus("Need profile and job before optimization.");
      return;
    }
    setStatus("Optimizing final application package...");
    try {
      const result = await careerApi.optimizeApplication({
        profile_id: profile.profile_id,
        job_id: job.job_id,
        company_context: company,
      });
      setOptimizedPackage(result);
      saveLocalState("career.optimized", result);
      refreshDashboardSnapshot();
      setStatus("Application package optimized.");
    } catch (error) {
      setStatus(error instanceof Error ? `Optimization failed: ${error.message}` : "Optimization failed.");
    }
  }

  return (
    <section className="space-y-6">
      <PageHeader
        title="Career Workflow"
        description="Single page flow: input -> jobs -> resume -> ATS -> outreach -> results."
      />

      <section className="output-card space-y-3">
        <h2 className="text-lg font-medium text-white">1) Profile Input</h2>
        <div className="grid gap-2 md:grid-cols-2">
          <input className="rounded bg-zinc-950 p-2" value={role} onChange={(e) => setRole(e.target.value)} placeholder="Target Role" />
          <input className="rounded bg-zinc-950 p-2" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company/Domain" />
          <input className="rounded bg-zinc-950 p-2" value={github} onChange={(e) => setGithub(e.target.value)} placeholder="GitHub URL" />
          <input className="rounded bg-zinc-950 p-2" value={linkedin} onChange={(e) => setLinkedin(e.target.value)} placeholder="LinkedIn URL" />
        </div>
        <textarea className="w-full rounded bg-zinc-950 p-2" rows={5} value={resumeText} onChange={(e) => setResumeText(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <button className="rounded bg-cyan-600 px-3 py-2 text-white" onClick={saveProfile}>Save Profile</button>
          <button
            className="rounded bg-emerald-600 px-3 py-2 text-white disabled:opacity-60"
            onClick={runFullWorkflow}
            disabled={runningAll}
          >
            {runningAll ? "Running..." : "Run Full Workflow"}
          </button>
        </div>
        <ProfileSummaryCard profile={dashboardSnapshot.profile as SavedProfile | null} />
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <StepCard title="2) Job Finder" onClick={fetchJobs} buttonText="Fetch Jobs">
          {jobs.length ? (
            <div className="space-y-2">
              {jobs.map((job) => (
                <div key={job.job_id} className="output-subcard">
                  <p className="text-sm font-medium text-zinc-100">{job.title} - {job.company}</p>
                  <div className="kv-row">
                    <span className="status-badge info">{(job.match_score * 100).toFixed(1)}% match</span>
                    <span className="text-xs text-zinc-400">{job.location}</span>
                  </div>
                  <a href={job.apply_link} className="text-xs text-cyan-300" target="_blank" rel="noreferrer">
                    Open listing
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No jobs fetched yet." />
          )}
        </StepCard>
        <StepCard title="3) Resume Builder (LaTeX + Overleaf)" onClick={generateResume} buttonText="Generate LaTeX Resume">
          {resumeSummary ? (
            <div className="space-y-2">
              <p className="text-sm text-zinc-300">{resumeSummary}</p>
              <p className={`status-badge ${pdfPath ? "success" : "warning"}`}>
                {pdfPath ? "LaTeX generated and PDF ready" : "LaTeX generated, PDF unavailable"}
              </p>
              {pdfPath ? <p className="text-xs text-cyan-300 break-all">{pdfPath}</p> : null}
              {overleafExport ? (
                <div className="space-y-2 pt-1">
                  <p className={`status-badge ${overleafExport.no_real_images_found ? "success" : "warning"}`}>
                    {overleafExport.no_real_images_found ? "No real images found" : "Image references detected"}
                  </p>
                  {overleafExport.warnings?.length ? (
                    <ul className="list-disc pl-5 text-xs text-yellow-300">
                      {overleafExport.warnings.map((w) => <li key={w}>{w}</li>)}
                    </ul>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <a className="rounded bg-cyan-600 px-3 py-2 text-white text-sm" href={overleafExport.overleaf_url} target="_blank" rel="noreferrer">
                      Open in Overleaf
                    </a>
                    <a className="rounded bg-zinc-700 px-3 py-2 text-white text-sm" href={overleafExport.tex_download_url} target="_blank" rel="noreferrer">
                      Download .tex
                    </a>
                    {overleafExport.pdf_download_url ? (
                      <a className="rounded bg-emerald-700 px-3 py-2 text-white text-sm" href={overleafExport.pdf_download_url} target="_blank" rel="noreferrer">
                        Download PDF
                      </a>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState text="No resume generated yet." />
          )}
        </StepCard>
        <StepCard title="4) ATS Analyzer" onClick={analyzeAts} buttonText="Analyze ATS">
          {atsScore !== null ? (
            <div className="space-y-2">
              <p className={`status-badge ${atsScore >= 85 ? "success" : atsScore >= 70 ? "warning" : "error"}`}>
                ATS Score: {atsScore}/100
              </p>
              <ul className="list-disc pl-5 text-xs text-zinc-300">
                {atsSuggestions.slice(0, 4).map((s) => <li key={s}>{s}</li>)}
              </ul>
            </div>
          ) : (
            <EmptyState text="No ATS report yet." />
          )}
        </StepCard>
        <StepCard title="5) Outreach" onClick={generateOutreach} buttonText="Generate Outreach">
          {contacts.length ? (
            <div className="space-y-2">
              <div className="output-subcard">
                {contacts.map((c, idx) => (
                  <div key={`${c.email}-${idx}`} className="kv-row">
                    <span className="text-sm text-zinc-200">{c.name} - {c.title}</span>
                    <span className={`status-badge ${c.email ? "info" : "warning"}`}>{c.email || "No real email found"}</span>
                  </div>
                ))}
              </div>
              {emailPreview ? <pre className="whitespace-pre-wrap text-xs text-zinc-300 output-subcard">{emailPreview}</pre> : null}
            </div>
          ) : (
            <EmptyState text="No outreach generated yet." />
          )}
        </StepCard>
        <StepCard title="6) Final Optimizer" onClick={optimizeApplicationPackage} buttonText="Optimize Application">
          {optimizedPackage ? (
            <div className="space-y-2">
              <div className="kv-row">
                <span className="status-badge success">ATS {optimizedPackage.estimated_ats_score}/100</span>
                <span className="status-badge info">Match {optimizedPackage.estimated_match_score}%</span>
              </div>
              <ul className="list-disc pl-5 text-xs text-zinc-300">
                {optimizedPackage.key_improvements.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <pre className="whitespace-pre-wrap text-xs text-zinc-300 output-subcard">{optimizedPackage.personalized_outreach_email}</pre>
            </div>
          ) : (
            <p className="text-sm text-zinc-300">No optimized package yet.</p>
          )}
        </StepCard>
      </div>

      <div className="output-card space-y-3">
        <div className="kv-row">
          <h2 className="text-lg font-medium text-white">8) Debug Snapshot</h2>
          <button
            type="button"
            className="rounded bg-zinc-800 px-3 py-1 text-xs text-zinc-100 hover:bg-zinc-700"
            onClick={() => setShowDebugSnapshot((prev) => !prev)}
          >
            {showDebugSnapshot ? "Hide Debug JSON" : "Show Debug JSON"}
          </button>
        </div>
        {showDebugSnapshot ? (
          <pre className="mt-2 whitespace-pre-wrap text-xs text-zinc-300">
            {mounted
              ? JSON.stringify(dashboardSnapshot, null, 2)
              : JSON.stringify(
                  {
                    input: null,
                    profile: null,
                    job: null,
                    resume: null,
                    ats: null,
                    outreach: null,
                    optimized: null,
                    overleaf: null,
                  },
                  null,
                  2
                )}
          </pre>
        ) : (
          <p className="text-sm text-zinc-400">Debug JSON is hidden by default.</p>
        )}
      </div>

      <p className="status-badge info">{status || "Ready"}</p>
    </section>
  );
}

function StepCard({
  title,
  buttonText,
  onClick,
  children,
}: {
  title: string;
  buttonText: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="output-card space-y-2">
      <h3 className="text-white font-medium">{title}</h3>
      <button className="rounded bg-cyan-600 px-3 py-2 text-white" onClick={onClick}>
        {buttonText}
      </button>
      <div>{children}</div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="text-sm text-zinc-400">{text}</p>;
}

function ProfileSummaryCard({ profile }: { profile: SavedProfile | null }) {
  return (
    <div className="output-subcard">
      <p className="text-sm text-zinc-200">Profile Status</p>
      {!profile?.profile_id ? (
        <p className="text-xs text-zinc-400 mt-1">No profile saved yet.</p>
      ) : (
        <div className="space-y-1 mt-1">
          <div className="kv-row">
            <span className="text-xs text-zinc-400">Profile ID</span>
            <span className="text-xs text-zinc-300">{profile.profile_id}</span>
          </div>
          <div className="kv-row">
            <span className="text-xs text-zinc-400">Readiness</span>
            <span className="status-badge info">{Math.round((profile.readiness_score || 0) * 100)}%</span>
          </div>
          <div className="flex flex-wrap gap-1 pt-1">
            {(profile.normalized_skills || []).slice(0, 8).map((skill) => (
              <span key={skill} className="status-badge info">{skill}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
