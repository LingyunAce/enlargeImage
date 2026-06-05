"use client";
import type { Job } from "@/lib/types";

interface Props {
  job: Job;
  onCancel: () => void;
}

export function ProgressPanel({ job, onCancel }: Props) {
  const pct = Math.round(job.progress * 100);
  return (
    <div className="card">
      <div className="row">
        <strong>Job {job.id.slice(0, 8)}</strong>
        <span>· {job.status}</span>
        {job.stage && <span>· {job.stage}</span>}
        <span style={{ marginLeft: "auto" }}>{pct}%</span>
        {(job.status === "queued" || job.status === "running") && (
          <button onClick={onCancel} style={{ background: "#cc4444" }}>
            Cancel
          </button>
        )}
      </div>
      <div className="bar"><div style={{ width: `${pct}%` }} /></div>
      {job.error && <p className="error">{job.error}</p>}
    </div>
  );
}
