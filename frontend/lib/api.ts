const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiGet(path: string) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`API GET failed: ${response.status}`);
  }

  return response.json();
}

export async function apiPost(path: string, body: unknown) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API POST failed: ${response.status}`);
  }
  return response.json();
}

export const careerApi = {
  ingestProfile: (payload: unknown) => apiPost("/api/profile/ingest", payload),
  searchJobs: (profileId: string, q: string, location: string) =>
    apiGet(`/api/jobs/search?profile_id=${encodeURIComponent(profileId)}&q=${encodeURIComponent(q)}&location=${encodeURIComponent(location)}`),
  generateResume: (payload: unknown) => apiPost("/api/resume/generate", payload),
  analyzeAts: (payload: unknown) => apiPost("/api/ats/analyze", payload),
  findEmployees: (company: string, jobId: string) =>
    apiGet(`/api/employees/find?company=${encodeURIComponent(company)}&job_id=${encodeURIComponent(jobId)}`),
  generateEmails: (payload: unknown) => apiPost("/api/emails/generate", payload),
  optimizeApplication: (payload: unknown) => apiPost("/api/application/optimize", payload),
  generateOverleafResume: (payload: unknown) => apiPost("/api/resume/overleaf/generate", payload),
  runPipeline: (payload: unknown) => apiPost("/api/pipeline/run", payload),
  getPipeline: (runId: string) => apiGet(`/api/pipeline/${runId}`),
  getOutreachSample: () => apiGet("/api/outreach/sample"),
  getJobResumePipelineSample: () => apiGet("/api/job-application/pipeline/sample"),
};

export function saveLocalState(key: string, value: unknown) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(key, JSON.stringify(value));
  }
}

export function loadLocalState<T>(key: string): T | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}
