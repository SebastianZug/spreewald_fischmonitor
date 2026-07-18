"""Rauch-Tests: Paket importierbar, Hintergrund-Funktion rechnet korrekt."""
import numpy as np

from fischzaehler.background import median_background


class _FakeCap:
    """Minimaler Ersatz fuer cv2.VideoCapture zum Testen von median_background."""

    def __init__(self, frames):
        self._frames = frames
        self._pos = 0

    def get(self, prop):
        # cv2.CAP_PROP_FRAME_COUNT == 7
        return len(self._frames) if prop == 7 else 0

    def set(self, prop, value):
        # cv2.CAP_PROP_POS_FRAMES == 1
        if prop == 1:
            self._pos = int(value)
        return True

    def read(self):
        if self._pos >= len(self._frames):
            return False, None
        f = self._frames[self._pos]
        self._pos += 1
        return True, f


def test_median_background_shape_and_dtype():
    frames = [np.full((4, 4, 3), v, dtype=np.uint8) for v in (10, 20, 30, 250)]
    bg = median_background(_FakeCap(frames), n_samples=4)
    assert bg.shape == (4, 4, 3)
    assert bg.dtype == np.uint8


def test_median_ignores_outlier_frame():
    # Drei ruhige Frames + ein heller Ausreisser -> Median bleibt beim Ruhewert
    frames = [np.full((2, 2, 3), 100, dtype=np.uint8) for _ in range(3)]
    frames.append(np.full((2, 2, 3), 255, dtype=np.uint8))
    bg = median_background(_FakeCap(frames), n_samples=4)
    assert int(bg.mean()) == 100
