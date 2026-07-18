"""Kosmetische Bildverbesserung fuer die *Anzeige* (nicht fuer die Detektion!).

Unterwasseraufnahmen sind truebe und gruenstichig (Rot wird im Wasser zuerst
absorbiert). Diese Aufbereitung -- Grauwelt-Weissabgleich gegen den Farbstich
plus CLAHE fuer lokalen Kontrast -- macht das 360deg-Video deutlich klarer.

Bewusst NUR aufs Ausgabebild anwenden: auf den Detektions-Input gelegt verstaerkt
CLAHE die Vegetationstextur und erzeugt massenhaft Fehlerkennungen (empirisch
geprueft). Die Detektion arbeitet weiter auf dem Rohbild.
"""
import cv2
import numpy as np

_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _gray_world(img, strength=0.6, lo=0.5, hi=2.0):
    """Grauwelt-Weissabgleich: Kanalmittel angleichen, gedaempft und begrenzt."""
    f = img.astype(np.float32)
    means = [f[:, :, c].mean() or 1.0 for c in range(3)]
    gray = sum(means) / 3
    for c in range(3):
        gain = np.clip(1 + (gray / means[c] - 1) * strength, lo, hi)
        f[:, :, c] *= gain
    return np.clip(f, 0, 255).astype(np.uint8)


def enhance(img, saturation=1.15):
    """Weissabgleich + CLAHE (+ leichte Saettigung) fuer klarere Darstellung."""
    img = _gray_world(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = _clahe.apply(l)
    out = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    if saturation != 1.0:
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return out
