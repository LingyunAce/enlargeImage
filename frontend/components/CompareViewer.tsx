"use client";
import { outputUrl } from "@/lib/api";
import type { Job } from "@/lib/types";

interface Props {
  job: Job;
  inputUrl: string | null;
}

export function CompareViewer({ job, inputUrl }: Props) {
  if (job.status !== "done") {
    return (
      <div className="card">
        <h2>Result</h2>
        <p>Not ready.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <h2>Result</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <p>Original</p>
          {inputUrl ? <img src={inputUrl} alt="original" /> : <p>(unavailable)</p>}
        </div>
        <div>
          <p>Upscaled ({job.scale}x)</p>
          <img src={outputUrl(job.id)} alt="upscaled" />
        </div>
      </div>
    </div>
  );
}
