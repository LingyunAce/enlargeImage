"use client";
import { useEffect, useRef, useState } from "react";
import { Uploader } from "@/components/Uploader";
import { ProgressPanel } from "@/components/ProgressPanel";
import { HistoryList } from "@/components/HistoryList";
import { CompareViewer } from "@/components/CompareViewer";
import { createJob, deleteJob, getJob, listJobs, pollJob } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<Job | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inputUrl, setInputUrl] = useState<string | null>(null);
  const pollAbort = useRef<AbortController | null>(null);

  const refresh = async () => {
    const list = await listJobs();
    setJobs(list);
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (selectedId) {
      const j = jobs.find((x) => x.id === selectedId);
      if (j) {
        setActive(j);
        if (j.status === "done") {
          // Fetch input blob for compare view
          fetch(`/api/jobs/${j.id}/output`).then((r) => {
            // not used; we use input blob instead. Re-fetch input via /output is for output only.
          });
        }
      }
    }
  }, [selectedId, jobs]);

  const onSubmit = async (file: File, scale: number) => {
    setInputUrl(URL.createObjectURL(file));
    const job = await createJob(file, scale);
    setActive(job);
    setSelectedId(job.id);
    await refresh();
    pollAbort.current = new AbortController();
    try {
      const final = await pollJob(
        job.id,
        (j) => setActive(j),
        pollAbort.current.signal,
      );
      setActive(final);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        console.error(e);
      }
    } finally {
      await refresh();
    }
  };

  const onCancel = async () => {
    if (active) {
      pollAbort.current?.abort();
      await deleteJob(active.id);
      await refresh();
    }
  };

  const onDelete = async (id: string) => {
    await deleteJob(id);
    if (selectedId === id) {
      setSelectedId(null);
      setActive(null);
    }
    await refresh();
  };

  return (
    <main>
      <Uploader disabled={!!active && active.status === "running"} onSubmit={onSubmit} />
      {active && <ProgressPanel job={active} onCancel={onCancel} />}
      {active && <CompareViewer job={active} inputUrl={inputUrl} />}
      <HistoryList
        jobs={jobs}
        selectedId={selectedId}
        onSelect={(id) => { setSelectedId(id); setActive(null); }}
        onDelete={onDelete}
      />
    </main>
  );
}
