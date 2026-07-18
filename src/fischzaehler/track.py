#!/usr/bin/env python3
"""Markiert und VERFOLGT bewegte Objekte (Fische) – Kamera muss stillstehen.

Gegenueber ``fisch-detect`` zusaetzlich:
  * Zentroid-Tracking ueber Frames (verbindet Erkennungen zu Spuren)
  * nur Spuren, die ueber >= MIN_HITS Frames bestehen, werden gezeichnet
    -> Flackern, Schwebteilchen und kurze Lichtreflexe fallen weg
  * jede Spur bekommt eine ID; Spuren mit genug Netto-Weg gelten als "Fisch"
  * live-Zaehler + Gesamtzahl eindeutiger Fisch-Spuren

Nutzung:
    fisch-track <in> <out> [--min A] [--max A] [--thresh T]
"""
import argparse
import json

import cv2

from .activity import activity_fraction, plant_mask
from .background import median_background
from .enhance import enhance
from .scale import REF_WIDTH, Scaler


class Track:
    __slots__ = ("id", "cx", "cy", "box", "hits", "misses", "start", "path", "drawn")

    def __init__(self, tid, cx, cy, box):
        self.id = tid
        self.cx, self.cy = cx, cy
        self.box = box
        self.hits = 1
        self.misses = 0
        self.start = (cx, cy)
        self.path = 0.0
        self.drawn = False


def main():
    ap = argparse.ArgumentParser(prog="fisch-track", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--min", type=int, default=40,
                    help=f"min. Blobflaeche (px bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--max", type=int, default=9000,
                    help=f"max. Blobflaeche (px bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--thresh", type=int, default=20)
    ap.add_argument("--max-dist", type=int, default=60,
                    help=f"max. px zwischen Frames (bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--min-hits", type=int, default=4, help="Frames bis Spur bestaetigt")
    ap.add_argument("--max-misses", type=int, default=8, help="Frames bis Spur verworfen")
    ap.add_argument("--move", type=int, default=25,
                    help=f"Netto-Weg fuer 'Fisch' (px bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--ignore-bright", type=int, default=256,
                    help="helle Bereiche > Wert ignorieren (Sonne/Kaustik); 256 = aus")
    ap.add_argument("--ref-width", type=int, default=REF_WIDTH,
                    help="Referenzbreite, auf der --min/--max/... getunt sind")
    ap.add_argument("--no-plant-mask", action="store_true",
                    help="Pflanzenmaske (schwankende Vegetation ausblenden) abschalten")
    ap.add_argument("--plant-persist", type=float, default=0.10,
                    help="Pixel gilt als Pflanze ab diesem Aktivitaets-Anteil (0..1)")
    ap.add_argument("--plant-overlap", type=float, default=0.5,
                    help="Detektion verwerfen, wenn Anteil in Pflanzenmaske > Wert")
    ap.add_argument("--enhance", action="store_true",
                    help="Ausgabevideo kosmetisch aufhellen/entfaerben (Detektion bleibt roh)")
    ap.add_argument("--stats-json", default=None,
                    help="JSON mit aktiven Fischen pro Frame schreiben (fuer den Web-Viewer)")
    ap.add_argument("--count-only", action="store_true",
                    help="kein Video schreiben, nur zaehlen (schnell)")
    ap.add_argument("--bin", type=int, default=60,
                    help="Histogramm-Fenster in Sekunden (Default 60)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.src)
    if not cap.isOpened():
        raise SystemExit(f"Konnte Video nicht oeffnen: {args.src}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    sc = Scaler(w, args.ref_width)
    min_area = sc.area_px(args.min)
    max_area = sc.area_px(args.max)
    max_dist = sc.length(args.max_dist)
    move_min = sc.length(args.move)
    blur_k = sc.blur_ksize()
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sc.morph_ksize(),) * 2)
    dil_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sc.blur_ksize(3),) * 2)
    lw = max(1, round(2 * sc.s))
    fscale = max(0.6, 0.8 * sc.s)

    print(f"Video {w}x{h} @ {fps:.1f}fps – Skalierung x{sc.s:.2f} "
          f"(Flaeche {min_area:.0f}..{max_area:.0f}px, Suchradius {max_dist:.0f}px, "
          f"Netto-Weg {move_min:.0f}px)")
    print("Hintergrund ...")
    bg_raw = median_background(cap)
    bg = cv2.GaussianBlur(bg_raw, (blur_k, blur_k), 0)

    pmask = None
    if not args.no_plant_mask:
        print("Pflanzenmaske (Aktivitaetskarte) ...")
        frac = activity_fraction(cap, bg_raw, args.thresh)
        pmask = plant_mask(frac, args.plant_persist, (w, h))
        cov = (pmask > 0).mean()
        print(f"  Pflanzenanteil der Flaeche: {cov*100:.1f}%")

    out = None if args.count_only else cv2.VideoWriter(
        args.dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    tracks = []
    next_id = 0
    fish_ids = set()
    hist = {}          # Bin-Index -> Anzahl neuer Fische
    fish_series = []   # aktive Fische pro Frame (fuer die Web-Zeitleiste)
    fnum = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fnum += 1
        blur = cv2.GaussianBlur(frame, (blur_k, blur_k), 0)
        g = cv2.cvtColor(cv2.absdiff(blur, bg), cv2.COLOR_BGR2GRAY)
        _, m = cv2.threshold(g, args.thresh, 255, cv2.THRESH_BINARY)
        if args.ignore_bright < 256:
            fgray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            m[fgray > args.ignore_bright] = 0
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, open_k)
        m = cv2.morphologyEx(m, cv2.MORPH_DILATE, dil_k, iterations=2)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        dets = []
        for c in cnts:
            a = cv2.contourArea(c)
            if a < min_area or a > max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            if pmask is not None:
                roi = pmask[y:y + bh, x:x + bw]
                if roi.size and (roi > 0).mean() > args.plant_overlap:
                    continue   # Detektion liegt in schwankender Vegetation
            dets.append((x + bw / 2, y + bh / 2, (x, y, bw, bh)))

        # greedy: jede Erkennung der naechsten Spur zuordnen
        for t in tracks:
            t.misses += 1
        used = set()
        for cx, cy, box in dets:
            best, bd = None, max_dist
            for t in tracks:
                d = ((t.cx - cx) ** 2 + (t.cy - cy) ** 2) ** 0.5
                if d < bd and id(t) not in used:
                    best, bd = t, d
            if best is not None:
                best.path += ((best.cx - cx) ** 2 + (best.cy - cy) ** 2) ** 0.5
                best.cx, best.cy, best.box = cx, cy, box
                best.hits += 1
                best.misses = 0
                used.add(id(best))
            else:
                tracks.append(Track(next_id, cx, cy, box))
                next_id += 1
        tracks = [t for t in tracks if t.misses <= args.max_misses]

        # Ausgabebild: Detektion lief auf dem Rohframe; hier optional aufhellen,
        # dann die Boxen darauf zeichnen (Boxfarben bleiben so unveraendert).
        canvas = (enhance(frame) if args.enhance else frame) if out is not None else None

        active = 0
        nfish_now = 0
        for t in tracks:
            if t.hits < args.min_hits:
                continue
            active += 1
            x, y, bw, bh = [int(v) for v in t.box]
            net = ((t.cx - t.start[0]) ** 2 + (t.cy - t.start[1]) ** 2) ** 0.5
            is_fish = net >= move_min
            if is_fish:
                nfish_now += 1
            if is_fish and t.id not in fish_ids:
                fish_ids.add(t.id)
                b = int((fnum / fps) // args.bin)
                hist[b] = hist.get(b, 0) + 1   # neuer Fisch in diesem Zeitfenster
            if canvas is not None:
                color = (60, 220, 60) if is_fish else (0, 200, 255)
                cv2.rectangle(canvas, (x, y), (x + bw, y + bh), color, lw)
                cv2.putText(canvas, f"#{t.id}", (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5 * sc.s, color, lw)

        fish_series.append(nfish_now)

        if canvas is not None:
            cv2.putText(canvas, f"aktiv: {active}   Fische gesamt: {len(fish_ids)}",
                        (12, round(30 * sc.s)), cv2.FONT_HERSHEY_SIMPLEX,
                        fscale, (60, 220, 60), lw)
            out.write(canvas)

    cap.release()
    if out is not None:
        out.release()
        print(f"Fertig -> {args.dst}")

    if args.stats_json:
        with open(args.stats_json, "w") as fh:
            json.dump({"fps": round(fps, 4), "frames": fnum,
                       "active_fish": fish_series}, fh)
        print(f"Statistik -> {args.stats_json}")
    print(f"Eindeutige Fisch-Spuren (Netto-Weg >= {move_min:.0f}px): {len(fish_ids)}")
    if hist:
        print(f"\nVerteilung ({args.bin}s-Fenster):")
        peak = max(hist.values())
        for b in range(max(hist) + 1):
            c = hist.get(b, 0)
            bar = "#" * int(40 * c / peak) if peak else ""
            t0 = b * args.bin
            print(f"  {t0//60:02d}:{t0%60:02d}  {c:4d}  {bar}")


if __name__ == "__main__":
    main()
