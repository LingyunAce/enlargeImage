"use client";
import { outputUrl } from "@/lib/api";
import type { Job } from "@/lib/types";

interface Props {
  jobs: Job[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function HistoryList({ jobs, selectedId, onSelect, onDelete }: Props) {
  return (
    <div className="card">
      <h2>History</h2>
      {jobs.length === 0 && <p>No jobs yet.</p>}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {jobs.map((j) => (
          <li
            key={j.id}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "8px 0",
              borderBottom: "1px solid #2a2c33",
              background: j.id === selectedId ? "#22252c" : undefined,
            }}
          >
            <button
              onClick={() => onSelect(j.id)}
              style={{ background: "transparent", color: "#4a8cff", textAlign: "left", flex: 1 }}
            >
              <code>{j.id.slice(0, 8)}</code> · {j.scale}x · {j.status}
            </button>
            {j.status === "done" && (
              <a
                href={outputUrl(j.id)}
                download={`enlarged-${j.id}.png`}
                style={{ color: "#4a8cff", marginRight: 8 }}
              >
                Download
              </a>
            )}
            <button onClick={() => onDelete(j.id)} style={{ background: "#444" }}>
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
