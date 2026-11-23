"""Runnable Mouche BLE / simulated foil-tip telemetry client."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from foil_tip_panel import CausalHitDetector, RingBuffer  # noqa: E402


def _popen_probe(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(timeout=10)
    return proc.returncode, out.strip(), err.strip()


def simulate_stream(samples_count: int = 120, fs_hz: float = 200.0, jerk_thr: float = 500.0) -> dict:
    rb = RingBuffer(maxlen=4096)
    det = CausalHitDetector(fs_hz=fs_hz, jerk_threshold=jerk_thr, refractory_ms=150.0)
    dt_ns = int(1e9 / fs_hz)
    t0 = time.perf_counter_ns()
    trace = []
    events = []

    for idx in range(samples_count):
        t_ns = t0 + idx * dt_ns
        ax = 0.0
        ay = 0.0
        az = 1.0
        mic_env = 0.05
        tip_open = 0

        if idx == max(1, samples_count // 3):
            ax = 15.0
            ay = 0.8
            mic_env = 0.90
            tip_open = 1
        elif idx == max(2, (2 * samples_count) // 3):
            ax = 7.2
            ay = 0.3
            mic_env = 0.65
            tip_open = 1

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

    return {
        "brand": "Mouche",
        "mode": "simulated_ble_stream",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "ring_buffer_samples": len(rb.snapshot()),
        "events": events,
        "trace": trace,
    }


async def scan_ble_devices(timeout_s: float = 3.0) -> list[dict]:
    try:
        from bleak import BleakScanner  # type: ignore
    except ImportError:
        return []
    found = await BleakScanner.discover(timeout=timeout_s)
    return [{"name": d.name or "<unnamed>", "address": d.address} for d in found]


def main() -> int:
    parser = argparse.ArgumentParser(description="Mouche BLE / simulated telemetry client")
    parser.add_argument("--simulate", action="store_true", help="Run deterministic synthetic BLE stream")
    parser.add_argument("--scan-only", action="store_true", help="Scan BLE peripherals via bleak if installed")
    parser.add_argument("--out", default="/tmp/mouche_session.json", help="Output session JSON path")
    args = parser.parse_args()

    rc, py_ver, _ = _popen_probe([sys.executable, "--version"])
    if args.scan_only:
        devices = asyncio.run(scan_ble_devices(timeout_s=2.0))
        print(json.dumps({"python": py_ver, "ble_devices": devices}, indent=2))
        return 0

    payload = simulate_stream()
    payload["python_runtime"] = py_ver if rc == 0 else "python"
    out_path = Path(args.out)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} with {len(payload['trace'])} samples and {len(payload['events'])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
