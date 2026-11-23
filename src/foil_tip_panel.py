"""Mouche foil-tip ring buffer, causal hit detector, and Popen launcher."""

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
        self._hist: deque = deque(maxlen=self.win + 1)
        self._last_event_ns: int = 0

    def update(self, t_ns: int, ax: float, ay: float, az: float):
        mag = float(np.sqrt(ax * ax + ay * ay + az * az))
        self._hist.append((t_ns, mag))
        if len(self._hist) < 2:
            return None
        dt = max(1e-6, (self._hist[-1][0] - self._hist[-2][0]) / 1e9)
        jerk = abs(self._hist[-1][1] - self._hist[-2][1]) / dt
        envelope = float(np.mean([m for _, m in self._hist]) ** 2)
        if t_ns - self._last_event_ns < self.refractory_ns:
            return None
        if jerk > self.jerk_thr:
            self._last_event_ns = t_ns
            label = "flick_candidate" if jerk > 2.0 * self.jerk_thr else "flat_hit_candidate"
            return HitCandidate(t_ns, mag, jerk, envelope, label)
        return None


def spawn_child_popen(cmd: list[str]) -> subprocess.Popen:
    """Launch a child process via `subprocess.Popen` (never `subprocess.run`)."""
    return subprocess.Popen(cmd)
