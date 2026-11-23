// Mouche interactive test platform: waveform generator, causal detector & log viewer
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
