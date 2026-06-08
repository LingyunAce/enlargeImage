"""Production startup script.

Scans models/ for SwinIR weights (named SwinIR_REALSR_X{scale}.pth) and
loads one SwinIRRunner per scale into a MultiRunner. Wires up the
FileStore, JobStore, JobManager, and runs uvicorn.

Usage:
    python run.py                          # defaults
    python run.py --port 9000              # custom port
    python run.py --model-dir /opt/models  # custom model dir
    python run.py --workers 4              # uvicorn workers (CPU only: use 1)
    python run.py --reload                 # dev mode with reload
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import uvicorn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EnlargeImage production server")
    p.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"),
                   help="Bind host (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")),
                   help="Bind port (default: 8000)")
    p.add_argument("--model-dir", default=os.getenv("MODEL_DIR", "./models"),
                   help="Directory containing SwinIR_REALSR_X{scale}.pth files")
    p.add_argument("--storage-dir", default=os.getenv("STORAGE_DIR", "./storage"),
                   help="Directory for per-job input/output files")
    p.add_argument("--db-path", default=os.getenv("DB_PATH", "./data.db"),
                   help="SQLite database file path")
    p.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", "1")),
                   help="Number of uvicorn workers (1 recommended for CPU)")
    p.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info"),
                   choices=["critical", "error", "warning", "info", "debug", "trace"])
    p.add_argument("--reload", action="store_true",
                   help="Enable auto-reload (dev mode)")
    p.add_argument("--no-models-ok", action="store_true",
                   help="Start even if no model weights are found (uses stub)")
    return p.parse_args()


def find_models(model_dir: str) -> dict[int, Path]:
    """Scan model_dir for SwinIR_REALSR_X{scale}.pth files."""
    found: dict[int, Path] = {}
    d = Path(model_dir)
    if not d.is_dir():
        return found
    for p in d.glob("SwinIR_REALSR_X*.pth"):
        # Filename like SwinIR_REALSR_X4.pth -> scale=4
        try:
            scale = int(p.stem.split("X")[-1])
        except (ValueError, IndexError):
            logging.warning("Skipping unrecognized model file: %s", p)
            continue
        if scale not in (2, 4, 8):
            logging.warning("Skipping model with unsupported scale %d: %s", scale, p)
            continue
        found[scale] = p
    return found


# URLs for the official SwinIR releases (Real-World Image SR)
_MODEL_URLS = {
    2: "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth",
    4: "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth",
    8: "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth",
}


def download_model(scale: int, dest_dir: str, log: logging.Logger) -> Path:
    """Download a SwinIR weight file with a simple progress indicator.

    Uses urllib (stdlib) so we don't need to add requests as a dep.
    """
    import shutil
    import urllib.request
    from urllib.error import URLError

    if scale not in _MODEL_URLS:
        raise ValueError(f"no URL known for scale={scale}")
    url = _MODEL_URLS[scale]
    dest = Path(dest_dir) / f"SwinIR_REALSR_X{scale}.pth"
    if dest.exists():
        log.info("Model already present: %s (%.1f MB)", dest, dest.stat().st_size / 1024 / 1024)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Downloading SwinIR X%d model from %s ...", scale, url)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        mb = downloaded / 1024 / 1024
                        total_mb = total / 1024 / 1024
                        print(f"\r  {pct:3d}%  {mb:5.1f} / {total_mb:5.1f} MB", end="", flush=True)
        print()  # newline after progress
    except URLError as e:
        if tmp.exists():
            tmp.unlink()
        log.error("Failed to download model: %s", e)
        log.error("Check your network connection, or manually download from:")
        log.error("  %s", url)
        log.error("And save to: %s", dest)
        raise
    shutil.move(str(tmp), str(dest))
    log.info("Downloaded %s (%.1f MB)", dest, dest.stat().st_size / 1024 / 1024)
    return dest


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("run")

    # Defer imports until after args parse (so --help is fast)
    from app.config import get_settings
    from app.pipeline.orchestrator import Pipeline
    from app.pipeline.runner import MultiRunner, SwinIRRunner
    from app.pipeline.seam import SeamBlender
    from app.pipeline.tiler import Tiler
    from app.services.file_store import FileStore
    from app.services.job_manager import JobManager
    from app.services.job_store import JobStore

    # Find or download model weights
    models = find_models(args.model_dir)
    use_stub = False
    if not models:
        if args.no_models_ok:
            log.warning("No model weights found in %s; using stub runner", args.model_dir)
            use_stub = True
        else:
            # Auto-download the X4 model (the most common case)
            log.info("No model weights found in %s; auto-downloading X4 ...", args.model_dir)
            try:
                download_model(4, args.model_dir, log)
                models = find_models(args.model_dir)
            except Exception:
                log.error("Auto-download failed. Pass --no-models-ok to use the stub runner instead.")
                return 2
            if not models:
                log.error("Still no models after download attempt. Giving up.")
                return 2

    if use_stub:
        from app.services.job_manager import _StubRunner
        runner = _StubRunner(scale=4)
    else:
        log.info("Loading SwinIR weights: %s", {s: str(p) for s, p in models.items()})
        runners = {
            scale: SwinIRRunner(model_path=str(p), scale=scale, device="cpu")
            for scale, p in models.items()
        }
        for r in runners.values():
            r.warmup()
        runner = MultiRunner(runners)
        log.info("Loaded %d runner(s), supported scales: %s", len(runners), runner.scale)

    # Wire up the pipeline and job manager
    settings = get_settings()
    pipeline = Pipeline(
        runner=runner,
        tiler=Tiler(tile_size=settings.tile_size, overlap=settings.overlap),
        blender=SeamBlender(),
    )
    jm = JobManager(
        store=JobStore(db_path=args.db_path),
        file_store=FileStore(root=args.storage_dir),
        pipeline=pipeline,
        flush_interval=settings.flush_interval,
        semaphore_permits=settings.semaphore_permits,
    )

    # Create the FastAPI app
    from app.main import create_app
    app = create_app(job_manager=jm)

    log.info("Starting uvicorn on %s:%d (workers=%d)", args.host, args.port, args.workers)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.log_level,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
