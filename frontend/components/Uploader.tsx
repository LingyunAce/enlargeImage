"use client";
import { useState } from "react";
import { SUPPORTED_SCALES } from "@/lib/types";

interface Props {
  disabled: boolean;
  onSubmit: (file: File, scale: number) => void;
}

export function Uploader({ disabled, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [scale, setScale] = useState<number>(4);

  return (
    <div className="card">
      <h1>EnlargeImage</h1>
      <div className="row">
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={disabled}
        />
        <label>
          Scale:&nbsp;
          <select
            value={scale}
            onChange={(e) => setScale(Number(e.target.value))}
            disabled={disabled}
          >
            {SUPPORTED_SCALES.map((s) => (
              <option key={s} value={s}>{s}x</option>
            ))}
          </select>
        </label>
        <button
          disabled={disabled || !file}
          onClick={() => file && onSubmit(file, scale)}
        >
          Upscale
        </button>
      </div>
    </div>
  );
}
