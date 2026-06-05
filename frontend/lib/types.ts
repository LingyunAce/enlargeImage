export type JobStatus = "queued" | "running" | "done" | "failed" | "canceled";
export type StageName = "tiling" | "inference" | "blending" | "encoding";

export interface Job {
  id: string;
  status: JobStatus;
  stage: StageName | null;
  progress: number;
  scale: number;
  error: string | null;
  createdAt: string;
  updatedAt: string;
}

export const SUPPORTED_SCALES: readonly number[] = [2, 4, 8];
