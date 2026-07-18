"""Gemeinsame Hilfsfunktion: Median-Hintergrund einer stillstehenden Kamera.

Da die Kamera fest steht, ist der zeitliche Median gleichmaessig verteilter
Frames eine gute Schaetzung der Szene ohne Fische.
"""
import cv2
import numpy as np


def median_background(cap, n_samples=40):
    """Median-Hintergrund aus ``n_samples`` gleichmaessig verteilten Frames.

    Setzt die Leseposition anschliessend wieder auf den Anfang zurueck.
    Gibt ein unbearbeitetes uint8-Bild zurueck; ein evtl. gewuenschter
    Weichzeichner ist Sache des Aufrufers.
    """
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    idxs = np.linspace(0, max(total - 1, 0), n_samples).astype(int)
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            frames.append(f)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return np.median(np.stack(frames), axis=0).astype(np.uint8)
