"""Build Mouche V3 unified Hero + Slider test platform (`docs/`) and `docs/downloads/`."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import subprocess
import sys
import zipfile

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


def prepare_downloads(docs_dir: Path) -> list[str]:
    dl_dir = docs_dir / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    sources = [
        ROOT / "src" / "foil_tip_panel.py",
        ROOT / "src" / "mouche_ble_client.py",
        Path(__file__).resolve(),
    ]
    copied = []
    for src_file in sources:
        if src_file.exists():
            dest = dl_dir / src_file.name
            dest.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(f"downloads/{dest.name}")

    zip_path = dl_dir / "mouche-bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in copied:
            f = docs_dir / rel
            zf.write(f, arcname=f"mouche/{Path(rel).name}")
        for asset_name in ("index.html", "mouche.css", "mouche.js", "build_manifest.json"):
            asset = docs_dir / asset_name
            if asset.exists():
                zf.write(asset, arcname=f"mouche/docs/{asset_name}")

    copied.append("downloads/mouche-bundle.zip")
    return copied


def run_test_suite() -> dict:
    rc, out, err = _popen_capture([sys.executable, "-c", "import numpy as np; print(np.__version__)"])
    np_version = out if rc == 0 else f"err({rc}):{err}"

    rb = RingBuffer(maxlen=4096)
    det = CausalHitDetector(fs_hz=200.0, energy_window_ms=20.0, jerk_threshold=500.0, refractory_ms=150.0)

    samples = [
        (1_000_000_000, 0.0, 0.0, 1.0, 0.05, 0),
        (1_005_000_000, 14.0, 1.0, 1.0, 0.88, 1),
        (1_025_000_000, 7.5, 0.5, 1.0, 0.40, 1),
        (1_250_000_000, 6.2, 0.2, 1.0, 0.72, 1),
        (1_270_000_000, 1.0, 0.0, 1.0, 0.06, 0),
    ]

    events = []
    trace = []
    for t_ns, ax, ay, az, mic_env, tip_open in samples:
        rb.push((t_ns, ax, ay, az, mic_env, tip_open))
        ev = det.update(t_ns, ax, ay, az, mic_env=mic_env, tip_open=tip_open)
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

    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    downloads = prepare_downloads(docs_dir)

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
        "downloads": downloads,
        "ring_buffer_samples": len(rb.snapshot()),
        "candidate_events": events,
        "default_trace": trace,
    }

    (docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    css_content = """/* Mouche V3 Unified Hero + Slider Telemetry Styles */
:root {
  --md-bg: #f3f6fa;
  --md-surface: #ffffff;
  --md-surface-2: #eef3f9;
  --md-ink: #0f172a;
  --md-ink-muted: #475569;
  --md-primary: #006a6a;
  --md-primary-container: #9cf1f0;
  --md-on-primary-container: #002020;
  --md-danger: #ba1a1a;
  --md-outline: #cbd5e1;
  --md-shadow-1: 0 2px 8px rgba(15, 23, 42, 0.06);
  --md-shadow-2: 0 10px 28px rgba(15, 23, 42, 0.12);
  --md-radius: 18px;
  --md-radius-sm: 12px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: radial-gradient(circle at 85% 5%, #d9f2ef 0%, var(--md-bg) 52%);
  color: var(--md-ink);
  font-family: "Inter", "Roboto", system-ui, -apple-system, sans-serif;
  line-height: 1.55;
}
.app-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  backdrop-filter: blur(12px);
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid var(--md-outline);
  padding: 0.8rem 1.25rem;
}
.app-bar-inner {
  max-width: 1160px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}
.brand-row { display: flex; align-items: center; gap: 0.65rem; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-weight: 700;
  font-size: 0.78rem;
  padding: 0.28rem 0.72rem;
  border-radius: 999px;
}
.chip.err { background: #fee2e2; color: var(--md-danger); }
.container {
  max-width: 1160px;
  margin: 1.25rem auto 3.5rem;
  padding: 0 1.25rem;
}
.mega-hero {
  background: var(--md-surface);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius);
  box-shadow: var(--md-shadow-2);
  overflow: hidden;
  margin-bottom: 1.25rem;
}
.hero-banner {
  background: linear-gradient(125deg, #004747 0%, #006a6a 60%, #1e40af 135%);
  color: #ffffff;
  padding: 1.6rem 1.75rem;
}
.hero-banner h1 { margin: 0.4rem 0 0.45rem; font-size: clamp(1.5rem, 3vw, 2.15rem); font-weight: 800; }
.hero-banner p { margin: 0; opacity: 0.94; max-width: 76ch; }
.hero-body { padding: 1.4rem 1.75rem; }
.explainer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 1.2rem;
}
.explainer-box {
  background: var(--md-surface-2);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  padding: 1rem 1.1rem;
}
.explainer-box h2 { margin: 0 0 0.4rem; font-size: 1.05rem; color: var(--md-primary); }
.explainer-box p { margin: 0; font-size: 0.92rem; }
.slider-panel {
  background: #f8fafc;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  padding: 1.1rem;
  margin-bottom: 1.1rem;
}
.sliders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 1rem;
  align-items: center;
  margin-bottom: 0.9rem;
}
.slider-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--md-ink-muted);
}
.slider-top { display: flex; justify-content: space-between; color: var(--md-ink); }
input[type="range"] { width: 100%; accent-color: var(--md-primary); cursor: pointer; }
.action-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
  margin-bottom: 0.8rem;
}
select {
  font: inherit;
  font-weight: 600;
  color: var(--md-ink);
  background: #ffffff;
  border: 1px solid var(--md-outline);
  border-radius: 8px;
  padding: 0.48rem 0.7rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  font: inherit;
  font-weight: 600;
  font-size: 0.88rem;
  padding: 0.5rem 0.95rem;
  border-radius: 999px;
  border: 1px solid var(--md-primary);
  background: var(--md-primary);
  color: #ffffff;
  cursor: pointer;
}
.btn.tonal { background: var(--md-surface-2); color: var(--md-ink); border-color: var(--md-outline); }
.scrub-readout {
  font-size: 0.85rem;
  background: var(--md-surface-2);
  border: 1px solid var(--md-outline);
  border-radius: 8px;
  padding: 0.55rem 0.8rem;
  margin-bottom: 0.85rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.legend { display: flex; flex-wrap: wrap; gap: 1rem; font-size: 0.82rem; color: var(--md-ink-muted); margin-bottom: 0.45rem; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.35rem; }
canvas {
  width: 100%;
  height: 250px;
  border-radius: var(--md-radius-sm);
  border: 1px solid var(--md-outline);
  background: #ffffff;
  display: block;
}
.media-credits {
  margin-top: 1.15rem;
  padding-top: 1rem;
  border-top: 1px solid var(--md-outline);
  font-size: 0.86rem;
  color: var(--md-ink-muted);
}
.media-credits ul { margin: 0.35rem 0 0; padding-left: 1.25rem; }
.surface-card {
  background: var(--md-surface);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--md-shadow-1);
  margin-bottom: 1.25rem;
}
table { width: 100%; border-collapse: collapse; margin-top: 0.6rem; font-size: 0.88rem; }
th, td { border-bottom: 1px solid var(--md-outline); padding: 0.5rem 0.55rem; text-align: left; }
th { color: var(--md-ink-muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.03em; }
code, pre {
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--md-surface-2);
  border-radius: 8px;
}
code { padding: 0.14rem 0.38rem; font-size: 0.85em; }
pre { padding: 0.9rem; overflow-x: auto; max-height: 260px; border: 1px solid var(--md-outline); }
"""
    (docs_dir / "mouche.css").write_text(css_content, encoding="utf-8")

    js_content = """// Mouche V3 unified Hero slider, waveform scrub, CSV/JSON parser & detector
let moucheState = {
  manifest: null,
  trace: [],
  events: [],
};

function computeMag(ax, ay, az) {
  return Math.sqrt(ax * ax + ay * ay + az * az);
}

function parseCsvTrace(csvText) {
  const lines = csvText.split(/\\r?\\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const idxT = headers.indexOf("t_ns");
  const idxAx = headers.indexOf("ax");
  const idxAy = headers.indexOf("ay");
  const idxAz = headers.indexOf("az");
  const idxMag = headers.indexOf("mag_g");
  const idxMic = headers.indexOf("mic_env");
  const idxTip = headers.indexOf("tip_open");

  const parsed = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",").map((c) => c.trim());
    const ax = idxAx >= 0 ? Number(cols[idxAx] || 0) : 0;
    const ay = idxAy >= 0 ? Number(cols[idxAy] || 0) : 0;
    const az = idxAz >= 0 ? Number(cols[idxAz] || 1) : 1;
    const tNs = idxT >= 0 && cols[idxT] ? Number(cols[idxT]) : (1_000_000_000 + (i - 1) * 5_000_000);
    const mag = idxMag >= 0 && cols[idxMag] !== "" ? Number(cols[idxMag]) : computeMag(ax, ay, az);
    const micEnv = idxMic >= 0 && cols[idxMic] !== "" ? Number(cols[idxMic]) : 0;
    const tipOpen = idxTip >= 0 && cols[idxTip] !== "" ? Number(cols[idxTip]) : 0;
    if (!Number.isNaN(tNs) && !Number.isNaN(mag)) {
      parsed.push({ t_ns: tNs, ax, ay, az, mag_g: mag, mic_env: micEnv, tip_open: tipOpen });
    }
  }
  return parsed;
}

function generateScenario(scenario, fsHz = 200) {
  const dt = 1 / fsHz;
  const totalSamples = Math.round(1.5 * fsHz);
  const t0 = 1_000_000_000;
  const rows = [];

  for (let i = 0; i < totalSamples; i++) {
    const tSec = i * dt;
    const tNs = Math.round(t0 + tSec * 1e9);
    let ax = 0.04 * Math.sin(2 * Math.PI * 3 * tSec);
    let ay = 0.02 * Math.cos(2 * Math.PI * 2 * tSec);
    let az = 1.0;
    let micEnv = 0.05;
    let tipOpen = 0;

    if (scenario === "flick" && tSec >= 0.35 && tSec <= 0.42) {
      const p = (tSec - 0.35) / 0.07;
      ax = 16.0 * Math.sin(Math.PI * p);
      micEnv = 0.92 * Math.sin(Math.PI * p);
      tipOpen = p > 0.35 ? 1 : 0;
    } else if (scenario === "flat_hit" && tSec >= 0.60 && tSec <= 0.72) {
      const p = (tSec - 0.60) / 0.12;
      ax = 7.5 * Math.sin(Math.PI * p);
      micEnv = 0.66 * Math.sin(Math.PI * p);
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
    } else if (scenario === "tip_contact_beat") {
      if (tSec >= 0.25 && tSec <= 0.30) {
        ax = 5.5 * Math.sin(Math.PI * ((tSec - 0.25) / 0.05));
        micEnv = 0.78;
      } else if (tSec >= 0.75 && tSec <= 0.82) {
        const p = (tSec - 0.75) / 0.07;
        ax = 13.5 * Math.sin(Math.PI * p);
        micEnv = 0.94;
        tipOpen = 1;
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
        const base = jerk > 2 * jerkThr ? "flick_candidate" : "flat_hit_candidate";
        const label = pt.tip_open ? `${base}_tip_contact` : ((pt.mic_env || 0) >= 0.5 ? `${base}_acoustic` : base);
        detected.push({
          t_ns: pt.t_ns,
          peak_g: mag,
          jerk_g_per_s: jerk,
          mic_env: pt.mic_env || 0,
          tip_open: pt.tip_open || 0,
          label,
        });
      }
    }
    prev = { t_ns: pt.t_ns, mag };
  }
  return detected;
}

function updateScrubReadout(trace, scrubIdx) {
  const el = document.getElementById("scrub-readout");
  if (!el || !trace.length) return;
  const clamped = Math.max(0, Math.min(trace.length - 1, scrubIdx));
  const pt = trace[clamped];
  const mag = typeof pt.mag_g === "number" ? pt.mag_g : computeMag(pt.ax, pt.ay, pt.az);
  el.innerHTML = `
    <span><strong>Sample:</strong> ${clamped + 1}/${trace.length}</span>
    <span><strong>t_ns:</strong> <code>${pt.t_ns}</code></span>
    <span><strong>Accel:</strong> ${mag.toFixed(2)} g</span>
    <span><strong>Mic Env:</strong> ${Number(pt.mic_env || 0).toFixed(2)}</span>
    <span><strong>Tip Open:</strong> ${pt.tip_open ? "YES (1)" : "NO (0)"}</span>
  `;
}

function drawTraceCanvas(trace, events, scrubIdx) {
  const canvas = document.getElementById("telemetry-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = "#e5e7eb";
  ctx.lineWidth = 1;
  for (let y = 22; y < h - 10; y += 44) {
    ctx.beginPath();
    ctx.moveTo(42, y);
    ctx.lineTo(w - 16, y);
    ctx.stroke();
  }

  if (!trace.length) return;
  const tStart = trace[0].t_ns;
  const tEnd = Math.max(tStart + 1, trace[trace.length - 1].t_ns);
  const maxMag = Math.max(2.0, ...trace.map((p) => p.mag_g || 1.0));

  ctx.strokeStyle = "#006a6a";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  trace.forEach((pt, idx) => {
    const x = 44 + ((pt.t_ns - tStart) / (tEnd - tStart)) * (w - 64);
    const y = h - 22 - (((pt.mag_g || 1.0) / maxMag) * (h - 44));
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.strokeStyle = "#d97706";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  trace.forEach((pt, idx) => {
    const x = 44 + ((pt.t_ns - tStart) / (tEnd - tStart)) * (w - 64);
    const y = h - 22 - (Math.min(1, pt.mic_env || 0) * (h - 44));
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  const clamped = Math.max(0, Math.min(trace.length - 1, scrubIdx));
  const scrubPt = trace[clamped];
  const sx = 44 + ((scrubPt.t_ns - tStart) / (tEnd - tStart)) * (w - 64);
  ctx.strokeStyle = "#2563eb";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(sx, 12);
  ctx.lineTo(sx, h - 14);
  ctx.stroke();

  ctx.fillStyle = "#ba1a1a";
  for (const ev of events) {
    const x = 44 + ((ev.t_ns - tStart) / (tEnd - tStart)) * (w - 64);
    const y = h - 22 - (Math.min(1, (ev.peak_g || 1.0) / maxMag) * (h - 44));
    ctx.beginPath();
    ctx.arc(x, y, 5.5, 0, Math.PI * 2);
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
      <td><span class="chip">${ev.label}</span></td>
    </tr>
  `).join("");
}

function syncSliderLabels() {
  const jerkVal = document.getElementById("jerk-slider")?.value || "500";
  const refrVal = document.getElementById("refractory-slider")?.value || "150";
  const massVal = document.getElementById("mass-slider")?.value || "486";
  const jerkLbl = document.getElementById("jerk-val");
  const refrLbl = document.getElementById("refractory-val");
  const massLbl = document.getElementById("mass-val");
  if (jerkLbl) jerkLbl.textContent = `${jerkVal} g/s`;
  if (refrLbl) refrLbl.textContent = `${refrVal} ms`;
  if (massLbl) massLbl.textContent = `${Number(massVal).toFixed(1)} g`;
}

function refreshHeroPlatform() {
  syncSliderLabels();
  const jerkThr = Number(document.getElementById("jerk-slider")?.value || 500);
  const refrMs = Number(document.getElementById("refractory-slider")?.value || 150);
  const massG = Number(document.getElementById("mass-slider")?.value || 486);

  const scrubSlider = document.getElementById("scrub-slider");
  if (scrubSlider) {
    scrubSlider.max = String(Math.max(0, moucheState.trace.length - 1));
  }
  const scrubIdx = Number(scrubSlider?.value || 0);

  const budgetEl = document.getElementById("mass-budget-status");
  if (budgetEl) {
    const rem = (500 - massG).toFixed(1);
    if (massG <= 500) {
      budgetEl.className = "chip";
      budgetEl.textContent = `FIE Mass OK: ${massG.toFixed(1)} g (${rem} g margin)`;
    } else {
      budgetEl.className = "chip err";
      budgetEl.textContent = `FIE Over Limit: ${massG.toFixed(1)} g (+${(-rem).toFixed(1)} g)`;
    }
  }

  const events = runCausalDetection(moucheState.trace, jerkThr, refrMs);
  moucheState.events = events;
  updateScrubReadout(moucheState.trace, scrubIdx);
  drawTraceCanvas(moucheState.trace, events, scrubIdx);
  renderEventsTable(events);
}

async function initMoucheV3() {
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
    const scrubSlider = document.getElementById("scrub-slider");
    if (scrubSlider) scrubSlider.value = "0";
    refreshHeroPlatform();
  });

  for (const id of ["jerk-slider", "refractory-slider", "mass-slider", "scrub-slider"]) {
    document.getElementById(id)?.addEventListener("input", refreshHeroPlatform);
  }

  document.getElementById("export-json-btn")?.addEventListener("click", () => {
    const payload = JSON.stringify({ events: moucheState.events, trace: moucheState.trace }, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mouche-v3-session.json";
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
        refreshHeroPlatform();
        return;
      }
    } catch (_notJson) {
      // Attempt CSV parsing below
    }
    const csvRows = parseCsvTrace(text);
    if (csvRows.length) {
      moucheState.trace = csvRows;
      refreshHeroPlatform();
    }
  });

  refreshHeroPlatform();
}

document.addEventListener("DOMContentLoaded", initMoucheV3);
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
  <div class="app-bar">
    <div class="app-bar-inner">
      <div class="brand-row">
        <span class="chip">MOUCHE V3</span>
        <strong>Foil Tip Bluetooth &amp; Contact Telemetry</strong>
      </div>
      <div id="mass-budget-status" class="chip">FIE Mass OK: 486.0 g (14.0 g margin)</div>
    </div>
  </div>

  <main class="container">
    <section class="mega-hero">
      <div class="hero-banner">
        <span class="chip">Unified Hero Lab &bull; Sliders + Explainer + Downloads</span>
        <h1>Mouche — Foil Tip Bluetooth &amp; Test Platform</h1>
        <p>Built via <code>src/build_site.py</code> at <code>{safe_built}</code> &bull; NumPy <code>{safe_np}</code> &bull; Ceiling &lt;500 g foil mass &amp; &gt;500 g tip spring break force.</p>
      </div>

      <div class="hero-body">
        <div class="explainer-grid">
          <div class="explainer-box">
            <h2>Etymology &amp; Tip Mechanics</h2>
            <p><strong>Mouche</strong> (French for <em>fly</em>) names a pinpoint training mark. Foil tips pair a plunger, insulator, barrel, screw, sleeve, pressure spring (&gt;500 g break force), and wire inside a &lt;500 g foil—favoring a thin wireless module and rigid-flex carrier over fragile WLCSP earbud harvesting.</p>
          </div>
          <div class="explainer-box">
            <h2>Accelerometer + Mic Spatial &amp; Contact Log</h2>
            <p><strong>Contact:</strong> Accel magnitude, jerk, squared window energy, and refractory gating paired with MEMS microphone transients and tip-switch state classify flicks, flat hits, and beats. <strong>Spatial:</strong> Gyro/accel pose and short impact-anchored arcs log relative motion while respecting integration drift limits.</p>
          </div>
        </div>

        <div class="slider-panel">
          <div class="sliders-grid">
            <label class="slider-item">
              <span class="slider-top"><span>Jerk Threshold</span><strong id="jerk-val">500 g/s</strong></span>
              <input id="jerk-slider" type="range" min="100" max="3000" step="50" value="500" />
            </label>
            <label class="slider-item">
              <span class="slider-top"><span>Refractory Window</span><strong id="refractory-val">150 ms</strong></span>
              <input id="refractory-slider" type="range" min="20" max="400" step="10" value="150" />
            </label>
            <label class="slider-item">
              <span class="slider-top"><span>Measured Foil Mass</span><strong id="mass-val">486.0 g</strong></span>
              <input id="mass-slider" type="range" min="420" max="530" step="0.5" value="486" />
            </label>
            <label class="slider-item">
              <span class="slider-top"><span>Trace Scrub Slider</span><strong>Sample Cursor</strong></span>
              <input id="scrub-slider" type="range" min="0" max="4" step="1" value="0" />
            </label>
          </div>

          <div class="action-strip">
            <select id="scenario-select" aria-label="Test Scenario">
              <option value="flick">Flick Impulse</option>
              <option value="flat_hit">Flat / Line Hit</option>
              <option value="blade_beat_ringing">Blade Beat + Ringing</option>
              <option value="tip_contact_beat">Beat + Tip Contact</option>
            </select>
            <button id="run-scenario-btn" class="btn" type="button">Simulate Scenario</button>
            <button id="export-json-btn" class="btn tonal" type="button">Export Session JSON</button>
            <a class="btn" href="downloads/mouche-bundle.zip" download>mouche-bundle.zip</a>
            <a class="btn tonal" href="downloads/mouche_ble_client.py" download>mouche_ble_client.py</a>
            <a class="btn tonal" href="downloads/foil_tip_panel.py" download>foil_tip_panel.py</a>
            <a class="btn tonal" href="downloads/build_site.py" download>build_site.py</a>
          </div>

          <div id="scrub-readout" class="scrub-readout"></div>

          <div class="legend">
            <span><i class="dot" style="background:#006a6a"></i>Accel Magnitude (g)</span>
            <span><i class="dot" style="background:#d97706"></i>MEMS Mic Envelope</span>
            <span><i class="dot" style="background:#2563eb"></i>Scrub Cursor</span>
            <span><i class="dot" style="background:#ba1a1a"></i>Detected Event</span>
          </div>

          <canvas id="telemetry-canvas" width="980" height="250"></canvas>
        </div>

        <div class="media-credits">
          <strong>Referenced Engineering Drawings, Hardware &amp; Motion Clips:</strong>
          <ul>
            <li>Foil point cross-section drawing: South African Fencing foil tip diagram (<code>https://saf.pairsite.com/foiltip.html</code>).</li>
            <li>6-DoF IMU X/Y/Z axis &amp; sensor reference: Adafruit 6-DoF IMU breakout module (<code>https://www.adafruit.com/product/3886</code>).</li>
            <li>Fencing foil point &amp; flick motion demos: YouTube search query <code>"fencing foil tip point flick hit action"</code>.</li>
          </ul>
        </div>
      </div>
    </section>

    <section class="surface-card">
      <h2>Detected Contact &amp; Flick Events</h2>
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

    <section class="surface-card">
      <h2>Inspect Local Session Log (CSV / JSON) &amp; Build Manifest</h2>
      <p>Run <code>python3 -B mouche_ble_client.py --simulate --format csv --out /tmp/mouche_sim.csv</code> (or <code>--connect &lt;ADDR&gt;</code> with <code>bleak</code>) and load the file below.</p>
      <input id="log-file-input" type="file" accept=".csv,.json,.txt" />
      <pre id="custom-log-view">No local session file loaded yet.</pre>
      <h3>Build Manifest (<code>docs/build_manifest.json</code>)</h3>
      <pre id="live-manifest-view">{safe_json}</pre>
    </section>
  </main>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    summary = run_test_suite()
    print("Built Mouche V3 unified Hero + Slider platform at", summary["built_at_utc"])
