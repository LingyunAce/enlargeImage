"use client";
import { useEffect, useRef, useState } from "react";
import { Uploader } from "@/components/Uploader";
import { ProgressPanel } from "@/components/ProgressPanel";
import { HistoryList } from "@/components/HistoryList";
import { CompareViewer } from "@/components/CompareViewer";
import { createJob, deleteJob, listJobs, pollJob } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<Job | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inputUrl, setInputUrl] = useState<string | null>(null);
  const inputUrlRef = useRef<string | null>(null);
  const pollAbort = useRef<AbortController | null>(null);
  const selectedIdRef = useRef<string | null>(null);

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
      }
    }
  }, [selectedId, jobs]);

  useEffect(() => {
    return () => {
      if (inputUrlRef.current) URL.revokeObjectURL(inputUrlRef.current);
    };
  }, []);

  const onSubmit = async (file: File, scale: number) => {
    if (inputUrlRef.current) URL.revokeObjectURL(inputUrlRef.current);
    const url = URL.createObjectURL(file);
    inputUrlRef.current = url;
    setInputUrl(url);
    const job = await createJob(file, scale);
    setActive(job);
    setSelectedId(job.id);
    selectedIdRef.current = job.id;  // NEW
    await refresh();
    pollAbort.current = new AbortController();
    try {
      const final = await pollJob(
        job.id,
        (j) => {
          // Only update if user hasn't selected a different job
          if (selectedIdRef.current === job.id) {
            setActive(j);
          }
        },
        pollAbort.current.signal,
      );
      if (selectedIdRef.current === job.id) {
        setActive(final);
      }
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
        onSelect={(id) => {
          selectedIdRef.current = id;
          setSelectedId(id);
          setActive(null);
          if (inputUrlRef.current) URL.revokeObjectURL(inputUrlRef.current);
          inputUrlRef.current = null;
          setInputUrl(null);
        }}
        onDelete={onDelete}
      />
    </main>
  );
}
