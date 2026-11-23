"""Build Mouche static site (`docs/index.html`, `docs/mouche.css`, `docs/mouche.js`) and manifest."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from foil_tip_panel import CausalHitDetector, RingBuffer  # noqa: E402


def _run_popen_probe(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(timeout=15)
    return proc.returncode, out.strip(), err.strip()


def build_mouche_site() -> dict:
    rc, out, err = _run_popen_probe([sys.executable, "-c", "import numpy as np; print(np.__version__)"])
    np_version = out if rc == 0 else f"err({rc}):{err}"

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
            events.append({
                "t_ns": ev.t_ns,
                "peak_g": ev.peak_g,
                "jerk_g_per_s": ev.jerk_g_per_s,
                "envelope_energy": ev.envelope_energy,
                "label": ev.label,
            })

    built_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "device": "Mouche",
        "project": "Mouche — Foil Tip Bluetooth & Contact/Spatial Telemetry",
        "etymology": "French 'mouche' (fly / small precision target on a training surface or plastron)",
        "built_at_utc": built_at,
        "numpy_version": np_version,
        "constraints": {
            "max_foil_mass_g": 500.0,
            "min_tip_spring_break_force_g": 500.0,
            "sensors": ["accelerometer_imu", "mems_microphone", "isolated_tip_contact"],
        },
        "ring_buffer_samples": len(rb.snapshot()),
        "detector_sample_rate_hz": det.fs,
        "candidate_events": events,
    }

    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    css_text = """/* Mouche Foil Tip Telemetry Stylesheet */
:root {
  --bg: #f8fafc;
  --fg: #0f172a;
  --muted: #475569;
  --card: #ffffff;
  --border: #cbd5e1;
  --accent: #0f766e;
  --code-bg: #f1f5f9;
}
body {
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--fg);
  max-width: 920px;
  margin: 2rem auto;
  padding: 0 1rem;
  line-height: 1.55;
}
header { border-bottom: 2px solid var(--border); padding-bottom: 1rem; margin-bottom: 1.5rem; }
.badge { display: inline-block; background: #ccfbf1; color: var(--accent); font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.85rem; }
section { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; margin-bottom: 1.25rem; }
h1, h2, h3 { margin-top: 0; }
code, pre { background: var(--code-bg); border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
code { padding: 0.15rem 0.35rem; }
pre { padding: 1rem; overflow-x: auto; }
"""
    (docs_dir / "mouche.css").write_text(css_text, encoding="utf-8")

    js_text = """// Mouche manifest loader & local CSV/JSON contact log inspector
async function initMoucheViewer() {
  const target = document.getElementById("live-manifest-view");
  const fileInput = document.getElementById("log-file-input");
  const customView = document.getElementById("custom-log-view");

  try {
    const resp = await fetch("build_manifest.json", { cache: "no-store" });
    if (resp.ok && target) {
      const data = await resp.json();
      target.textContent = JSON.stringify(data, null, 2);
    }
  } catch (err) {
    if (target) {
      target.textContent = "Manifest fetch fallback: " + String(err);
    }
  }

  if (fileInput && customView) {
    fileInput.addEventListener("change", async (ev) => {
      const file = ev.target.files && ev.target.files[0];
      if (!file) return;
      const text = await file.text();
      customView.textContent = text.slice(0, 8000);
    });
  }
}

document.addEventListener("DOMContentLoaded", initMoucheViewer);
"""
    (docs_dir / "mouche.js").write_text(js_text, encoding="utf-8")

    safe_built = html.escape(built_at)
    safe_np = html.escape(np_version)
    safe_json = html.escape(json.dumps(manifest, indent=2))

    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mouche — Foil Tip Bluetooth &amp; Telemetry Overview</title>
  <link rel="stylesheet" href="mouche.css" />
  <script src="mouche.js" defer></script>
</head>
<body>
  <header>
    <span class="badge">Mouche Foil Tip Telemetry</span>
    <h1>Mouche — Foil Tip Bluetooth &amp; Telemetry Overview</h1>
    <p><strong>Status:</strong> Built cleanly via <code>src/build_site.py</code> at <code>{safe_built}</code>.</p>
  </header>

  <section>
    <h2>Etymology &amp; Foil Tip Context</h2>
    <p><strong>Mouche</strong> (French for <em>fly</em>) denotes a small precision target on a training surface or plastron. Existing foil tips combine a spring-loaded plunger, barrel, and scoring circuit under strict FIE limits (&lt;500 g total foil mass, &gt;500 g tip spring break force) and tight internal tip volume.</p>
    <p>Rather than fragile hot-air reflow harvesting of WLCSP earbud dies, Mouche favors an ultra-thin wireless module, rigid-flex carrier, strain-relieved thin pouch cell, isolated tip contact sense, and mechanical shock hardening.</p>
  </section>

  <section>
    <h2>Accelerometer + Microphone: Contact &amp; Spatial Logging</h2>
    <ul>
      <li><strong>Contact Logging:</strong> Accelerometer magnitude, jerk, and window energy separate flicks from flat hits with refractory gating, while a MEMS microphone captures acoustic/vibration contact transients (plunger seating, blade beats, surface impacts) alongside tip switch state.</li>
      <li><strong>Spatial Logging:</strong> Accelerometer + gyroscope orientation/pose and short-interval impact/motion-anchored arcs log relative tip kinematics, while explicitly accounting for double-integration drift when global room coordinates are not externally anchored.</li>
    </ul>
  </section>

  <section>
    <h2>Build Telemetry &amp; Manifest</h2>
    <ul>
      <li><strong>NumPy runtime:</strong> <code>{safe_np}</code></li>
      <li><strong>RingBuffer test count:</strong> <code>{len(rb.snapshot())}</code> samples</li>
      <li><strong>Detector rate:</strong> <code>{det.fs} Hz</code> (candidate events detected in synthetic pulse: <code>{len(events)}</code>)</li>
      <li><strong>Manifest file:</strong> <a href="build_manifest.json"><code>build_manifest.json</code></a></li>
    </ul>
    <pre id="live-manifest-view">{safe_json}</pre>
    <h3>Inspect Local Session Log (CSV / JSON)</h3>
    <input id="log-file-input" type="file" accept=".csv,.json,.txt" />
    <pre id="custom-log-view">No local session file loaded yet.</pre>
  </section>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    summary = build_mouche_site()
    print("Built Mouche site artifacts at", summary["built_at_utc"])
