"""Compile static site (`docs/index.html`) and manifest (`docs/build_manifest.json`)."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from foil_tip_panel import CausalHitDetector, RingBuffer  # noqa: E402


def run_build() -> dict:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import numpy as np; print(np.__version__)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(timeout=15)
    np_version = out.strip() if proc.returncode == 0 else f"err({proc.returncode}):{err.strip()}"

    rb = RingBuffer(maxlen=256)
    det = CausalHitDetector(fs_hz=200.0, jerk_threshold=500.0)
    samples = [
        (1_000_000_000, 0.0, 0.0, 1.0),
        (1_005_000_000, 12.0, 0.0, 1.0),
        (1_010_000_000, 1.0, 0.0, 1.0),
    ]
    events = []
    for t_ns, ax, ay, az in samples:
        rb.push((t_ns, ax, ay, az))
        ev = det.update(t_ns, ax, ay, az)
        if ev is not None:
            events.append({"t_ns": ev.t_ns, "peak_g": ev.peak_g, "label": ev.label})

    built_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "project": "Foil Tip Bluetooth & Telemetry Overview",
        "built_at_utc": built_at,
        "numpy_version": np_version,
        "ring_buffer_samples": len(rb.snapshot()),
        "detector_sample_rate_hz": det.fs,
        "candidate_events": events,
    }

    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    safe_built = html.escape(built_at)
    safe_np = html.escape(np_version)
    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Foil Tip Bluetooth &amp; Telemetry Overview</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 840px; margin: 2.5rem auto; padding: 0 1rem; line-height: 1.5; }}
    code, pre {{ background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 4px; }}
    pre {{ padding: 1rem; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Foil Tip Bluetooth &amp; Telemetry Overview</h1>
  <p><strong>Status:</strong> Built cleanly via <code>src/build_site.py</code> at <code>{safe_built}</code>.</p>
  <ul>
    <li><strong>NumPy runtime:</strong> <code>{safe_np}</code></li>
    <li><strong>RingBuffer test count:</strong> <code>{len(rb.snapshot())}</code> samples</li>
    <li><strong>Detector rate:</strong> <code>{det.fs} Hz</code> (candidate events detected in synthetic pulse: <code>{len(events)}</code>)</li>
    <li><strong>Manifest:</strong> <a href="build_manifest.json"><code>build_manifest.json</code></a></li>
  </ul>
  <pre>{html.escape(json.dumps(manifest, indent=2))}</pre>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = run_build()
    print("Built docs/index.html and docs/build_manifest.json at", result["built_at_utc"])
