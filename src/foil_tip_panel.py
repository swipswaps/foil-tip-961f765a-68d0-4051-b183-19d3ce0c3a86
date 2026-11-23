"""Mouche foil-tip ring buffer, O(1) causal hit/flick detector, and Popen runner."""

from collections import deque
from dataclasses import dataclass
import subprocess
import numpy as np


@dataclass
class HitCandidate:
    t_ns: int
    peak_g: float
    jerk_g_per_s: float
    envelope_energy: float
    label: str


class RingBuffer:
    def __init__(self, maxlen: int = 4096):
        self._buf: deque = deque(maxlen=maxlen)

    def push(self, sample: tuple) -> None:
        self._buf.append(sample)

    def snapshot(self) -> list:
        return list(self._buf)


class CausalHitDetector:
    def __init__(
        self,
        fs_hz: float = 200.0,
        energy_window_ms: float = 20.0,
        jerk_threshold: float = 500.0,
        refractory_ms: float = 150.0,
    ):
        self.fs = fs_hz
        self.win = max(1, int(fs_hz * energy_window_ms / 1000.0))
        self.jerk_thr = jerk_threshold
        self.refractory_ns = int(refractory_ms * 1e6)
        self._hist: deque = deque(maxlen=self.win)
        self._mag_sum: float = 0.0
        self._prev_sample: tuple | None = None
        self._last_event_ns: int = -10**18

    def update(self, t_ns: int, ax: float, ay: float, az: float, mic_env: float = 0.0, tip_open: int = 0):
        mag = float(np.sqrt(ax * ax + ay * ay + az * az))
        if len(self._hist) == self._hist.maxlen:
            oldest_mag = self._hist[0][1]
            self._mag_sum -= oldest_mag
        self._hist.append((t_ns, mag))
        self._mag_sum += mag

        prev = self._prev_sample
        self._prev_sample = (t_ns, mag)
        if prev is None:
            return None

        dt = max(1e-6, (t_ns - prev[0]) / 1e9)
        jerk = abs(mag - prev[1]) / dt
        mean_mag = self._mag_sum / max(1, len(self._hist))
        envelope = float(mean_mag * mean_mag)

        if (t_ns - self._last_event_ns) < self.refractory_ns:
            return None

        if jerk > self.jerk_thr:
            self._last_event_ns = t_ns
            base = "flick_candidate" if jerk > 2.0 * self.jerk_thr else "flat_hit_candidate"
            if tip_open:
                label = f"{base}_tip_contact"
            elif mic_env >= 0.5:
                label = f"{base}_acoustic"
            else:
                label = base
            return HitCandidate(t_ns, mag, jerk, envelope, label)
        return None


def spawn_with_popen(cmd: list[str]) -> subprocess.Popen:
    """Spawn a child process via `subprocess.Popen` (never `subprocess.run`)."""
    return subprocess.Popen(cmd)
