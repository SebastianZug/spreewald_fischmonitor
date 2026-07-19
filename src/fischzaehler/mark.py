#!/usr/bin/env python3
"""``fisch-mark`` – manuelle Einzelobjekt-Markierung eines Fisches.

Fuer klare, sonnige Szenen, in denen die automatische Bewegungsdetektion
(``fisch-track``) an Kaustik, Blendung und driftenden Partikeln scheitert:
Hier gibt man EINEN bekannten Fisch per Startbox vor, ein Korrelationstracker
(MIL) folgt ihm vorwaerts UND rueckwaerts durch den Clip. Ergebnis: genau eine
rote Box ("manuelle Identifikation").

Wichtig: MIL meldet selbst nie "verloren" -- er haelt immer irgendeine Box.
Damit die Markierung nur erscheint, solange der Fisch wirklich da ist, wird an
der Box per Median-Hintergrund geprueft, ob dort ein Vordergrund-Objekt sitzt.
Faellt die Praesenz ueber mehrere Frames weg (Fisch aus dem Bild), endet die
Markierung.

Nutzung:
    fisch-mark <in> <out> --seed FRAME --box X Y W H [--enhance]
"""
import argparse
import json

import cv2

from .background import median_background
from .enhance import enhance
from .scale import Scaler

RED = (0, 0, 235)   # BGR


def _present(frame, bg, box, thresh, min_presence):
    """Sitzt an ``box`` ein Vordergrund-Objekt (Fisch)? -> bool."""
    x, y, w, h = [int(v) for v in box]
    x, y = max(0, x), max(0, y)
    roi_f = frame[y:y + h, x:x + w]
    roi_b = bg[y:y + h, x:x + w]
    if roi_f.size == 0 or roi_f.shape != roi_b.shape:
        return False
    d = cv2.cvtColor(cv2.absdiff(roi_f, roi_b), cv2.COLOR_BGR2GRAY)
    return (d > thresh).mean() >= min_presence


def track_object(cap, seed, box, bg, thresh, min_presence, max_miss):
    """MIL-Tracker ab ``seed`` vorwaerts + rueckwaerts, praesenz-begrenzt.

    Nur Frames, in denen an der Box wirklich ein Vordergrund-Objekt sitzt,
    werden markiert; nach ``max_miss`` Frames ohne Praesenz endet die Spur.
    """
    boxes = {seed: tuple(box)}

    for direction in (+1, -1):
        tr = cv2.TrackerMIL_create()
        cap.set(cv2.CAP_PROP_POS_FRAMES, seed)
        ok, f = cap.read()
        tr.init(f, tuple(box))
        fno, miss = seed, 0
        while True:
            fno += direction
            if fno < 0:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, fno)
            ok, f = cap.read()
            if not ok:
                break
            ok2, b = tr.update(f)
            if not ok2:
                break
            if _present(f, bg, b, thresh, min_presence):
                boxes[fno] = b
                miss = 0
            else:
                miss += 1
                if miss >= max_miss:
                    break
    return boxes


def main():
    ap = argparse.ArgumentParser(prog="fisch-mark", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--box", type=int, nargs=4, default=None, metavar=("X", "Y", "W", "H"),
                    help="Box um den Fisch (Pixel; Box-/Tracker-Modus)")
    ap.add_argument("--label", default="manuelle Identifikation")
    # Tracker-Modus (MIL folgt dem Fisch ab --seed):
    ap.add_argument("--seed", type=int, default=None,
                    help="Tracker-Modus: Frame-Nr. der Startbox")
    ap.add_argument("--presence-thresh", type=int, default=22,
                    help="Diff-Schwelle fuer Vordergrund an der Box")
    ap.add_argument("--min-presence", type=float, default=0.08,
                    help="min. Vordergrund-Anteil der Box, damit der Fisch als da gilt")
    ap.add_argument("--max-miss", type=int, default=10,
                    help="Frames ohne Praesenz, bis die Markierung endet")
    # Manueller Modus (feste/interpolierte Box ueber einen Frame-Bereich, ohne Tracker):
    ap.add_argument("--start", type=int, default=None, help="manueller Modus: erster Frame")
    ap.add_argument("--end", type=int, default=None, help="manueller Modus: letzter Frame")
    ap.add_argument("--box-to", type=int, nargs=4, default=None, metavar=("X", "Y", "W", "H"),
                    help="manueller Modus: End-Box; Box wird von --box dorthin interpoliert")
    # Marker-Modus (statischer Punkt-Marker statt Box):
    ap.add_argument("--marker", type=int, nargs=2, default=None, metavar=("X", "Y"),
                    help="statischer Ring-Marker an (X,Y) statt Box (hilft, den Fisch zu finden)")
    ap.add_argument("--enhance", action="store_true",
                    help="Ausgabevideo kosmetisch aufhellen/entfaerben")
    ap.add_argument("--stats-json", default=None,
                    help="JSON mit Objekt-Praesenz pro Frame (fuer den Web-Viewer)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.src)
    if not cap.isOpened():
        raise SystemExit(f"Konnte Video nicht oeffnen: {args.src}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    sc = Scaler(w)
    lw = max(2, round(3 * sc.s))
    fscale = max(0.7, 0.9 * sc.s)

    boxes = {}          # frame -> (x,y,w,h)  (Box-/Tracker-Modus)
    marker_frames = set()

    if args.marker is not None:
        # Marker-Modus: statischer Ring an (X,Y) ueber einen Frame-Bereich.
        lo = args.start if args.start is not None else 0
        hi = args.end if args.end is not None else max(0, n - 1)
        marker_frames = set(range(lo, hi + 1))
        print(f"Video {w}x{h} @ {fps:.1f}fps – statischer Marker bei "
              f"({args.marker[0]},{args.marker[1]}) Frame {lo}..{hi}")
    elif args.start is not None and args.end is not None:
        # Manueller Modus: feste (oder von --box nach --box-to interpolierte) Box.
        a, b = args.box, (args.box_to or args.box)
        span = max(1, args.end - args.start)
        for f in range(args.start, args.end + 1):
            t = (f - args.start) / span
            boxes[f] = tuple(a[i] + (b[i] - a[i]) * t for i in range(4))
        print(f"Video {w}x{h} @ {fps:.1f}fps – manuelle Box Frame "
              f"{args.start}..{args.end} ({args.start/fps:.1f}s..{args.end/fps:.1f}s)")
    else:
        if args.seed is None or args.box is None:
            raise SystemExit("Modus waehlen: --marker X Y | --box … --start/--end | --box … --seed")
        print(f"Video {w}x{h} @ {fps:.1f}fps – Hintergrund + Verfolgung ab Frame {args.seed} ...")
        bg = median_background(cap)
        boxes = track_object(cap, args.seed, args.box, bg,
                             args.presence_thresh, args.min_presence, args.max_miss)
        lo, hi = min(boxes), max(boxes)
        print(f"  Fisch praesent: Frame {lo}..{hi} "
              f"({lo/fps:.1f}s..{hi/fps:.1f}s, {len(boxes)} von {hi-lo+1} Frames markiert)")

    out = cv2.VideoWriter(args.dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    mr = max(24, round(60 * sc.s))     # Ring-Radius
    series = []
    fno = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fno += 1
        canvas = enhance(frame) if args.enhance else frame
        if args.marker is not None:
            present = fno in marker_frames
            if present:
                mx, my = int(args.marker[0]), int(args.marker[1])
                cv2.circle(canvas, (mx, my), mr, RED, lw)
                cv2.circle(canvas, (mx, my), max(3, round(5 * sc.s)), RED, -1)
                cv2.putText(canvas, args.label, (mx + mr + 12, my),
                            cv2.FONT_HERSHEY_SIMPLEX, fscale, RED, lw)
        else:
            present = fno in boxes
            if present:
                x, y, bw, bh = [int(v) for v in boxes[fno]]
                cv2.rectangle(canvas, (x, y), (x + bw, y + bh), RED, lw)
                cv2.putText(canvas, args.label, (x, max(0, y - 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, fscale, RED, lw)
        series.append(1 if present else 0)
        out.write(canvas)
    cap.release()
    out.release()
    print(f"Fertig -> {args.dst}")

    if args.stats_json:
        with open(args.stats_json, "w") as fh:
            json.dump({"fps": round(fps, 4), "frames": len(series),
                       "active_fish": series}, fh)
        print(f"Statistik -> {args.stats_json}")


if __name__ == "__main__":
    main()
