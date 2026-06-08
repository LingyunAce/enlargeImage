import type { Job } from "./types";

const API_BASE = "/api";

async function jsonOrThrow<T>(r: Response): Promise<T> {
  // Read the body once as text, then try to parse as JSON.
  // A Response body stream can only be consumed once, so we must not
  // call r.json() and r.text() sequentially.
  const text = await r.text();
  if (!r.ok) {
    // Error path: try to surface structured JSON if the server gave it,
    // otherwise fall back to the raw text (HTML error page, plain string, etc.)
    let body: unknown = text;
    try { body = JSON.parse(text); } catch { /* keep as text */ }
    throw new ApiError(r.status, body);
  }
  // Success path: parse the text we already have
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(r.status, text);
  }
}

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: unknown) {
    super(`API error ${status}: ${JSON.stringify(body)}`);
  }
}

export async function listJobs(limit = 20): Promise<Job[]> {
  return jsonOrThrow<Job[]>(await fetch(`${API_BASE}/jobs?limit=${limit}`));
}

export async function getJob(id: string): Promise<Job> {
  return jsonOrThrow<Job>(await fetch(`${API_BASE}/jobs/${id}`));
}

export async function createJob(file: File, scale: number): Promise<Job> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("scale", String(scale));
  return jsonOrThrow<Job>(await fetch(`${API_BASE}/jobs`, { method: "POST", body: fd }));
}

export async function deleteJob(id: string): Promise<void> {
  const r = await fetch(`${API_BASE}/jobs/${id}`, { method: "DELETE" });
  if (!r.ok && r.status !== 404) {
    throw new ApiError(r.status, await r.text());
  }
}

export function outputUrl(id: string): string {
  return `${API_BASE}/jobs/${id}/output`;
}

/** Poll a job until it reaches a terminal state. */
export async function pollJob(
  id: string,
  onUpdate: (j: Job) => void,
  signal: AbortSignal,
  intervalMs = 1000,
): Promise<Job> {
  while (true) {
    const j = await getJob(id);
    onUpdate(j);
    if (j.status === "done" || j.status === "failed" || j.status === "canceled") {
      return j;
    }
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(resolve, intervalMs);
      signal.addEventListener("abort", () => {
        clearTimeout(t);
        reject(new DOMException("aborted", "AbortError"));
      });
    });
  }
}
