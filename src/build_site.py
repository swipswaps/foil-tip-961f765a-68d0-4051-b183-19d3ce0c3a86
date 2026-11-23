"""Build the interactive Mouche test platform (`docs/`) and `docs/build_manifest.json`."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from foil_tip_panel import CausalHitDetector, RingBuffer  # noqa: E402


def _popen_capture(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(timeout=15)
    return proc.returncode, out.strip(), err.strip()


def run_test_suite() -> dict:
    rc, out, err = _popen_capture([sys.executable, "-c", "import numpy as np; print(np.__version__)"])
    np_version = out if rc == 0 else f"err({rc}):{err}"

    rb = RingBuffer(maxlen=4096)
    det = CausalHitDetector(fs_hz=200.0, energy_window_ms=20.0, jerk_threshold=500.0, refractory_ms=150.0)

    # Synthetic sequence covering: baseline, sharp flick, 20ms later ringing
    # (suppressed by 150ms refractory window), and a later flat hit.
    samples = [
        (1_000_000_000, 0.0, 0.0, 1.0, 0.05, 0),
        (1_005_000_000, 14.0, 1.0, 1.0, 0.85, 1),
        (1_025_000_000, 7.5, 0.5, 1.0, 0.40, 1),
        (1_250_000_000, 6.2, 0.2, 1.0, 0.65, 1),
        (1_270_000_000, 1.0, 0.0, 1.0, 0.06, 0),
    ]

    events = []
    trace = []
    for t_ns, ax, ay, az, mic_env, tip_open in samples:
        rb.push((t_ns, ax, ay, az, mic_env, tip_open))
        ev = det.update(t_ns, ax, ay, az)
        mag = float((ax * ax + ay * ay + az * az) ** 0.5)
        trace.append({
            "t_ns": t_ns,
            "ax": ax,
            "ay": ay,
            "az": az,
            "mag_g": mag,
            "mic_env": mic_env,
            "tip_open": tip_open,
        })
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
        "brand": "Mouche",
        "title": "Mouche — Foil Tip Bluetooth & Test Platform",
        "etymology": "French 'mouche' (fly / small precision target on a training surface or plastron)",
        "built_at_utc": built_at,
        "numpy_version": np_version,
        "constraints": {
            "max_foil_mass_g": 500.0,
            "min_tip_spring_break_force_g": 500.0,
            "sensors": ["accelerometer_imu", "mems_microphone", "isolated_tip_contact"],
        },
        "detector_config": {
            "fs_hz": det.fs,
            "energy_window_ms": 20.0,
            "jerk_threshold": det.jerk_thr,
            "refractory_ms": 150.0,
        },
        "ring_buffer_samples": len(rb.snapshot()),
        "candidate_events": events,
        "default_trace": trace,
    }

    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    css_content = """/* Mouche Foil Tip Test Platform Styles */
:root {
  --bg: #f8fafc;
  --fg: #0f172a;
  --muted: #475569;
  --card: #ffffff;
  --border: #cbd5e1;
  --accent: #0f766e;
  --accent-soft: #ccfbf1;
  --code-bg: #f1f5f9;
}
* { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--fg);
  max-width: 1040px;
  margin: 2rem auto;
  padding: 0 1rem 3rem;
  line-height: 1.5;
}
header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  border-bottom: 2px solid var(--border);
  padding-bottom: 1rem;
  margin-bottom: 1.25rem;
}
.pill {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 700;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  font-size: 0.85rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
  gap: 1rem;
  margin-bottom: 1.25rem;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.1rem;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.9rem;
}
label { display: inline-flex; flex-direction: column; font-size: 0.85rem; color: var(--muted); gap: 0.2rem; }
input, select, button {
  font: inherit;
  padding: 0.4rem 0.65rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--fg);
}
button {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  font-weight: 600;
  cursor: pointer;
}
button.secondary { background: #fff; color: var(--fg); border-color: var(--border); }
canvas {
  width: 100%;
  height: 260px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #ffffff;
  display: block;
}
table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.9rem; }
th, td { border-bottom: 1px solid var(--border); padding: 0.45rem 0.5rem; text-align: left; }
code, pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--code-bg);
  border-radius: 4px;
}
code { padding: 0.15rem 0.35rem; }
pre { padding: 0.9rem; overflow-x: auto; max-height: 280px; }
"""
    (docs_dir / "mouche.css").write_text(css_content, encoding="utf-8")

    js_content = """// Mouche interactive test platform: waveform generator, causal detector & log viewer
let moucheState = {
  manifest: null,
  trace: [],
  events: [],
};

function computeMag(ax, ay, az) {
  return Math.sqrt(ax * ax + ay * ay + az * az);
}

function generateScenario(scenario, fsHz = 200) {
  const dt = 1 / fsHz;
  const totalSamples = Math.round(1.5 * fsHz);
  const t0 = 1_000_000_000;
  const rows = [];

  for (let i = 0; i < totalSamples; i++) {
    const tSec = i * dt;
    const tNs = Math.round(t0 + tSec * 1e9);
    let ax = 0.05 * Math.sin(2 * Math.PI * 3 * tSec);
    let ay = 0.03 * Math.cos(2 * Math.PI * 2 * tSec);
    let az = 1.0;
    let micEnv = 0.05;
    let tipOpen = 0;

    if (scenario === "flick" && tSec >= 0.35 && tSec <= 0.42) {
      const p = (tSec - 0.35) / 0.07;
      ax = 16.0 * Math.sin(Math.PI * p);
      micEnv = 0.92 * Math.sin(Math.PI * p);
      tipOpen = p > 0.4 ? 1 : 0;
    } else if (scenario === "flat_hit" && tSec >= 0.60 && tSec <= 0.72) {
      const p = (tSec - 0.60) / 0.12;
      ax = 7.5 * Math.sin(Math.PI * p);
      micEnv = 0.65 * Math.sin(Math.PI * p);
      tipOpen = p > 0.25 ? 1 : 0;
    } else if (scenario === "blade_beat_ringing") {
      if (tSec >= 0.30 && tSec <= 0.34) {
        ax = 11.0 * Math.sin(Math.PI * ((tSec - 0.30) / 0.04));
        micEnv = 0.88;
      } else if (tSec > 0.34 && tSec <= 0.46) {
        const decay = Math.exp(-(tSec - 0.34) * 28);
        ax = 6.5 * decay * Math.sin(2 * Math.PI * 55 * (tSec - 0.34));
        micEnv = 0.45 * decay;
      }
    }

    rows.push({
      t_ns: tNs,
      ax,
      ay,
      az,
      mag_g: computeMag(ax, ay, az),
      mic_env: micEnv,
      tip_open: tipOpen,
    });
  }
  return rows;
}

function runCausalDetection(trace, jerkThr, refractoryMs) {
  const refractoryNs = refractoryMs * 1e6;
  let lastEventNs = -Infinity;
  let prev = null;
  const detected = [];

  for (const pt of trace) {
    const mag = typeof pt.mag_g === "number" ? pt.mag_g : computeMag(pt.ax, pt.ay, pt.az);
    if (prev !== null) {
      const dtS = Math.max(1e-6, (pt.t_ns - prev.t_ns) / 1e9);
      const jerk = Math.abs(mag - prev.mag) / dtS;
      if (pt.t_ns - lastEventNs >= refractoryNs && jerk > jerkThr) {
        lastEventNs = pt.t_ns;
        detected.push({
          t_ns: pt.t_ns,
          peak_g: mag,
          jerk_g_per_s: jerk,
          mic_env: pt.mic_env || 0,
          tip_open: pt.tip_open || 0,
          label: jerk > 2 * jerkThr ? "flick_candidate" : "flat_hit_candidate",
        });
      }
    }
    prev = { t_ns: pt.t_ns, mag };
  }
  return detected;
}

function drawTraceCanvas(trace, events) {
  const canvas = document.getElementById("telemetry-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  for (let y = 20; y < h; y += 45) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  if (!trace.length) return;
  const tStart = trace[0].t_ns;
  const tEnd = Math.max(tStart + 1, trace[trace.length - 1].t_ns);
  const maxMag = Math.max(2.0, ...trace.map((p) => p.mag_g || 1.0));

  ctx.strokeStyle = "#0f766e";
  ctx.lineWidth = 2;
  ctx.beginPath();
  trace.forEach((pt, idx) => {
    const x = 40 + ((pt.t_ns - tStart) / (tEnd - tStart)) * (w - 60);
    const y = h - 24 - (((pt.mag_g || 1.0) / maxMag) * (h - 48));
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.strokeStyle = "#d97706";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  trace.forEach((pt, idx) => {
    const x = 40 + ((pt.t_ns - tStart) / (tEnd - tStart)) * (w - 60);
    const y = h - 24 - (Math.min(1, pt.mic_env || 0) * (h - 48));
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#dc2626";
  for (const ev of events) {
    const x = 40 + ((ev.t_ns - tStart) / (tEnd - tStart)) * (w - 60);
    const y = h - 24 - (Math.min(1, (ev.peak_g || 1.0) / maxMag) * (h - 48));
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function renderEventsTable(events) {
  const tbody = document.getElementById("events-tbody");
  if (!tbody) return;
  if (!events.length) {
    tbody.innerHTML = "<tr><td colspan='5'>No candidate events above threshold.</td></tr>";
    return;
  }
  tbody.innerHTML = events.map((ev) => `
    <tr>
      <td><code>${ev.t_ns}</code></td>
      <td>${Number(ev.peak_g).toFixed(2)} g</td>
      <td>${Number(ev.jerk_g_per_s).toFixed(1)} g/s</td>
      <td>${Number(ev.mic_env || 0).toFixed(2)}</td>
      <td><strong>${ev.label}</strong></td>
    </tr>
  `).join("");
}

function refreshTestPlatform() {
  const jerkThr = Number(document.getElementById("jerk-thr-input")?.value || 500);
  const refrMs = Number(document.getElementById("refractory-ms-input")?.value || 150);
  const massG = Number(document.getElementById("foil-mass-input")?.value || 486);
  const budgetEl = document.getElementById("mass-budget-status");
  if (budgetEl) {
    const rem = (500 - massG).toFixed(1);
    budgetEl.textContent = massG <= 500
      ? `FIE Mass OK: ${massG.toFixed(1)} g (${rem} g remaining under 500 g limit)`
      : `FIE Mass OVER LIMIT: ${massG.toFixed(1)} g (+${(-rem).toFixed(1)} g over 500 g)`;
  }

  const events = runCausalDetection(moucheState.trace, jerkThr, refrMs);
  moucheState.events = events;
  drawTraceCanvas(moucheState.trace, events);
  renderEventsTable(events);
}

async function initMouchePlatform() {
  const manifestPre = document.getElementById("live-manifest-view");
  try {
    const resp = await fetch("build_manifest.json", { cache: "no-store" });
    if (resp.ok) {
      const data = await resp.json();
      moucheState.manifest = data;
      moucheState.trace = Array.isArray(data.default_trace) ? data.default_trace : [];
      if (manifestPre) manifestPre.textContent = JSON.stringify(data, null, 2);
    }
  } catch (err) {
    if (manifestPre) manifestPre.textContent = "Manifest fallback error: " + String(err);
  }

  if (!moucheState.trace.length) {
    moucheState.trace = generateScenario("flick");
  }

  document.getElementById("run-scenario-btn")?.addEventListener("click", () => {
    const scen = document.getElementById("scenario-select")?.value || "flick";
    moucheState.trace = generateScenario(scen);
    refreshTestPlatform();
  });

  for (const id of ["jerk-thr-input", "refractory-ms-input", "foil-mass-input"]) {
    document.getElementById(id)?.addEventListener("input", refreshTestPlatform);
  }

  document.getElementById("export-json-btn")?.addEventListener("click", () => {
    const payload = JSON.stringify({ events: moucheState.events, trace: moucheState.trace }, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mouche-test-session.json";
    a.click();
    URL.revokeObjectURL(url);
  });

  const fileInput = document.getElementById("log-file-input");
  const customView = document.getElementById("custom-log-view");
  fileInput?.addEventListener("change", async (ev) => {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    const text = await file.text();
    if (customView) customView.textContent = text.slice(0, 8000);
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed.trace)) {
        moucheState.trace = parsed.trace;
        refreshTestPlatform();
      }
    } catch (_ignored) {
      // Non-JSON or CSV preview remains visible in custom-log-view
    }
  });

  refreshTestPlatform();
}

document.addEventListener("DOMContentLoaded", initMouchePlatform);
"""
    (docs_dir / "mouche.js").write_text(js_content, encoding="utf-8")

    safe_built = html.escape(built_at)
    safe_np = html.escape(np_version)
    safe_json = html.escape(json.dumps(manifest, indent=2))

    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mouche — Foil Tip Bluetooth &amp; Test Platform</title>
  <link rel="stylesheet" href="mouche.css" />
  <script src="mouche.js" defer></script>
</head>
<body>
  <header>
    <div>
      <span class="pill">Mouche Test Platform</span>
      <h1>Mouche — Foil Tip Bluetooth &amp; Telemetry Overview</h1>
      <p>Built cleanly via <code>src/build_site.py</code> at <code>{safe_built}</code> &bull; NumPy <code>{safe_np}</code></p>
    </div>
    <div id="mass-budget-status" class="pill">FIE Mass OK: 486.0 g (14.0 g remaining under 500 g limit)</div>
  </header>

  <div class="grid">
    <div class="card">
      <h2>Etymology &amp; Tip Design</h2>
      <p><strong>Mouche</strong> (French for <em>fly</em>) refers to a precision target on a training surface or plastron. Existing foil tips pair a spring-loaded plunger (&gt;500 g break force) and scoring circuit inside a &lt;500 g foil.</p>
      <p>Mouche avoids fragile hot-air reflow harvesting of WLCSP earbud dies in favor of a compact wireless module, rigid-flex carrier, strain-relieved thin pouch cell, and isolated tip sense.</p>
    </div>
    <div class="card">
      <h2>Accelerometer + Microphone Logging</h2>
      <p><strong>Contact:</strong> Accelerometer magnitude, jerk, and window energy with refractory gating plus MEMS microphone transients and tip-switch state log flicks, flat hits, and blade beats.</p>
      <p><strong>Spatial:</strong> Gyro/accel pose and short impact-anchored arcs capture relative tip kinematics while guarding against double-integration drift.</p>
    </div>
  </div>

  <section class="card">
    <h2>Interactive Foil-Tip Test Platform</h2>
    <div class="controls">
      <label>Test Scenario
        <select id="scenario-select">
          <option value="flick">Flick Impulse</option>
          <option value="flat_hit">Flat / Line Hit</option>
          <option value="blade_beat_ringing">Blade Beat + Ringing</option>
        </select>
      </label>
      <label>Jerk Threshold (g/s)
        <input id="jerk-thr-input" type="number" step="50" value="500" />
      </label>
      <label>Refractory (ms)
        <input id="refractory-ms-input" type="number" step="10" value="150" />
      </label>
      <label>Measured Foil Mass (g)
        <input id="foil-mass-input" type="number" step="0.5" value="486" />
      </label>
      <button id="run-scenario-btn" type="button">Simulate Scenario</button>
      <button id="export-json-btn" class="secondary" type="button">Export Session JSON</button>
    </div>

    <canvas id="telemetry-canvas" width="960" height="260"></canvas>

    <table>
      <thead>
        <tr>
          <th>Timestamp (ns)</th>
          <th>Peak Accel</th>
          <th>Jerk</th>
          <th>Mic Env</th>
          <th>Classification</th>
        </tr>
      </thead>
      <tbody id="events-tbody"></tbody>
    </table>
  </section>

  <section class="card">
    <h2>Inspect Local Session Log &amp; Build Manifest</h2>
    <input id="log-file-input" type="file" accept=".csv,.json,.txt" />
    <pre id="custom-log-view">No local session file loaded yet.</pre>
    <h3>Build Manifest (<code>docs/build_manifest.json</code>)</h3>
    <pre id="live-manifest-view">{safe_json}</pre>
  </section>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    summary = run_test_suite()
    print("Built Mouche test platform at", summary["built_at_utc"])
