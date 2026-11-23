// Mouche manifest loader & local CSV/JSON contact log inspector
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
