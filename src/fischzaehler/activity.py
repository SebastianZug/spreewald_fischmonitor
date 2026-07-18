"""Pflanzen-/Dynamik-Maske aus zeitlicher Bewegungs-Haeufigkeit.

Schwankende Wasserpflanzen erzeugen zwar Bewegung, aber *ortsfest und dauerhaft*:
derselbe Pixel weicht in einem grossen Anteil aller Frames vom Median-Hintergrund
ab. Ein durchziehender Fisch aktiviert einen Pixel dagegen nur kurz. Der pro Pixel
akkumulierte Aktivitaets-Anteil ergibt deshalb eine interpretierbare Pflanzenkarte;
Detektionen, die ueberwiegend in dieser Maske liegen, werden als Vegetation verworfen.

Verwandt mit adaptiven Hintergrundmodellen (MOG2/KNN), aber explizit und
anschaubar -- man kann die Karte direkt visualisieren.
"""
import cv2
import numpy as np


def activity_fraction(cap, bg, thresh, proc_width=1920, step=3, blur_k=5):
    """Pro-Pixel-Anteil der Frames, in denen der Pixel "aktiv" ist.

    Rechnet auf reduzierter Breite ``proc_width`` (deutlich schneller; die Karte
    ist raeumlich grob genug). Liest das Video einmal komplett und setzt die
    Leseposition anschliessend auf 0 zurueck.

    Rueckgabe: float32-Karte in Verarbeitungsaufloesung (Werte 0..1).
    """
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pw = min(proc_width, w)
    ph = max(1, round(h * pw / w))
    bg_s = cv2.GaussianBlur(cv2.resize(bg, (pw, ph)), (blur_k, blur_k), 0)

    acc = np.zeros((ph, pw), np.float32)
    cnt = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if fi % step == 0:
            s = cv2.GaussianBlur(cv2.resize(frame, (pw, ph)), (blur_k, blur_k), 0)
            d = cv2.cvtColor(cv2.absdiff(s, bg_s), cv2.COLOR_BGR2GRAY)
            _, m = cv2.threshold(d, thresh, 255, cv2.THRESH_BINARY)
            acc += m > 0
            cnt += 1
        fi += 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return acc / max(cnt, 1)


def plant_mask(frac, persist, out_size):
    """Binaere Pflanzenmaske (uint8 0/255) in ``out_size=(W, H)``.

    Ein Pixel gilt als Pflanze, wenn er in mehr als ``persist`` Anteil der Frames
    aktiv war. Ein Close fuellt Loecher, ein Dilate gibt etwas Sicherheitsrand.
    """
    m = (frac > persist).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    return cv2.resize(m, out_size, interpolation=cv2.INTER_NEAREST)
