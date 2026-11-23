"""Runnable Mouche BLE GATT notify & simulated telemetry client (JSON & CSV)."""

import argparse
import asyncio
import csv
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


def parse_ble_payload(raw: bytes, fallback_t_ns: int) -> dict:
    """Parse ASCII/CSV or JSON BLE notification payload (`t_ns,ax,ay,az,mic_env,tip_open`)."""
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("{"):
        obj = json.loads(text)
        ax = float(obj.get("ax", 0.0))
        ay = float(obj.get("ay", 0.0))
        az = float(obj.get("az", 1.0))
        return {
            "t_ns": int(obj.get("t_ns", fallback_t_ns)),
            "ax": ax,
            "ay": ay,
            "az": az,
            "mag_g": float((ax * ax + ay * ay + az * az) ** 0.5),
            "mic_env": float(obj.get("mic_env", 0.0)),
            "tip_open": int(obj.get("tip_open", 0)),
        }
    parts = [p.strip() for p in text.split(",") if p.strip()]
    ax = float(parts[1]) if len(parts) > 1 else 0.0
    ay = float(parts[2]) if len(parts) > 2 else 0.0
    az = float(parts[3]) if len(parts) > 3 else 1.0
    t_ns = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else fallback_t_ns
    mic_env = float(parts[4]) if len(parts) > 4 else 0.0
    tip_open = int(float(parts[5])) if len(parts) > 5 else 0
    return {
        "t_ns": t_ns,
        "ax": ax,
        "ay": ay,
        "az": az,
        "mag_g": float((ax * ax + ay * ay + az * az) ** 0.5),
        "mic_env": mic_env,
        "tip_open": tip_open,
    }


def simulate_stream(samples_count: int = 160, fs_hz: float = 200.0, jerk_thr: float = 500.0) -> dict:
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
            ax = 15.5
            ay = 0.7
            mic_env = 0.92
            tip_open = 1
        elif idx == max(2, (3 * samples_count) // 4):
            ax = 7.4
            ay = 0.2
            mic_env = 0.68
            tip_open = 1

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

    return {
        "brand": "Mouche",
        "mode": "simulated_ble_stream",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "ring_buffer_samples": len(rb.snapshot()),
        "events": events,
        "trace": trace,
    }


async def stream_ble_notify(address: str, char_uuid: str, duration_s: float = 5.0, jerk_thr: float = 500.0) -> dict:
    try:
        from bleak import BleakClient  # type: ignore
    except ImportError as exc:
        raise RuntimeError("bleak is not installed; install with `pip install bleak` or use --simulate") from exc

    rb = RingBuffer(maxlen=4096)
    det = CausalHitDetector(fs_hz=200.0, jerk_threshold=jerk_thr, refractory_ms=150.0)
    trace: list[dict] = []
    events: list[dict] = []

    def on_notify(_sender, data: bytearray) -> None:
        pt = parse_ble_payload(bytes(data), time.perf_counter_ns())
        rb.push((pt["t_ns"], pt["ax"], pt["ay"], pt["az"], pt["mic_env"], pt["tip_open"]))
        trace.append(pt)
        ev = det.update(pt["t_ns"], pt["ax"], pt["ay"], pt["az"], mic_env=pt["mic_env"], tip_open=pt["tip_open"])
        if ev is not None:
            events.append({
                "t_ns": ev.t_ns,
                "peak_g": ev.peak_g,
                "jerk_g_per_s": ev.jerk_g_per_s,
                "envelope_energy": ev.envelope_energy,
                "label": ev.label,
            })

    async with BleakClient(address) as client:
        await client.start_notify(char_uuid, on_notify)
        await asyncio.sleep(max(0.1, duration_s))
        await client.stop_notify(char_uuid)

    return {
        "brand": "Mouche",
        "mode": "ble_gatt_notify",
        "address": address,
        "char_uuid": char_uuid,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "ring_buffer_samples": len(rb.snapshot()),
        "events": events,
        "trace": trace,
    }


def write_csv(path: Path, trace: list[dict]) -> None:
    fieldnames = ["t_ns", "ax", "ay", "az", "mag_g", "mic_env", "tip_open"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in trace:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


async def scan_ble_devices(timeout_s: float = 3.0) -> tuple[bool, list[dict]]:
    try:
        from bleak import BleakScanner  # type: ignore
    except ImportError:
        return False, []
    found = await BleakScanner.discover(timeout=timeout_s)
    return True, [{"name": d.name or "<unnamed>", "address": d.address} for d in found]


def main() -> int:
    parser = argparse.ArgumentParser(description="Mouche BLE GATT / simulated telemetry client")
    parser.add_argument("--simulate", action="store_true", help="Run deterministic synthetic BLE stream")
    parser.add_argument("--scan-only", action="store_true", help="Scan BLE peripherals via bleak")
    parser.add_argument("--connect", default="", help="BLE peripheral MAC/UUID address for GATT notify")
    parser.add_argument("--char-uuid", default="6e400003-b5a3-f393-e0a9-e50e24dcca9e", help="GATT notify characteristic UUID")
    parser.add_argument("--duration-s", type=float, default=5.0, help="Capture duration in seconds for --connect")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format")
    parser.add_argument("--out", default="/tmp/mouche_session.json", help="Output path")
    args = parser.parse_args()

    rc, py_ver, _ = _popen_probe([sys.executable, "--version"])
    if args.scan_only:
        ble_ok, devices = asyncio.run(scan_ble_devices(timeout_s=2.0))
        print(json.dumps({"python": py_ver, "bleak_available": ble_ok, "ble_devices": devices}, indent=2))
        return 0 if ble_ok else 2

    if args.connect:
        try:
            payload = asyncio.run(stream_ble_notify(args.connect, args.char_uuid, duration_s=args.duration_s))
        except Exception as exc:
            print(f"BLE connect failed: {exc}", file=sys.stderr)
            return 2
    else:
        payload = simulate_stream()

    payload["python_runtime"] = py_ver if rc == 0 else "python"
    out_path = Path(args.out)
    if args.format == "csv":
        write_csv(out_path, payload["trace"])
    else:
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({args.format}, mode={payload['mode']}) with {len(payload['trace'])} samples and {len(payload['events'])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
