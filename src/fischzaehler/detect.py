#!/usr/bin/env python3
"""Markiert bewegte Objekte (Fische) in Aufnahmen einer STILLSTEHENDEN Kamera.

Ansatz: Hintergrund-Subtraktion. Da die Kamera fest steht, ist der zeitliche
Median vieler Frames ~ die Szene ohne Fische. Jeder Frame wird dagegen
verglichen; was sich abhebt und in eine plausible Größe faellt, wird als
Fisch markiert.

Nutzung:
    fisch-detect <video_in> <video_out> [--min AREA] [--max AREA]

Beispiel:
    fisch-detect clips/demo.mp4 demo_marked.mp4
"""
import argparse

import cv2

from .background import median_background
from .scale import REF_WIDTH, Scaler


def main():
    ap = argparse.ArgumentParser(prog="fisch-detect", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--min", type=int, default=60,
                    help=f"min. Blobflaeche (px bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--max", type=int, default=8000,
                    help=f"max. Blobflaeche (px bei {REF_WIDTH}px-Referenz)")
    ap.add_argument("--thresh", type=int, default=22, help="Diff-Schwelle 0-255")
    ap.add_argument("--ref-width", type=int, default=REF_WIDTH,
                    help="Referenzbreite, auf der --min/--max/... getunt sind")
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
    blur_k = sc.blur_ksize()
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sc.morph_ksize(),) * 2)
    dil_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sc.blur_ksize(3),) * 2)

    print(f"Video {w}x{h} @ {fps:.1f}fps – Skalierung x{sc.s:.2f} "
          f"(Flaeche {min_area:.0f}..{max_area:.0f}px, Blur {blur_k})")
    print("berechne Hintergrund ...")
    bg_blur = cv2.GaussianBlur(median_background(cap), (blur_k, blur_k), 0)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.dst, fourcc, fps, (w, h))
    lw = max(1, round(2 * sc.s))          # Strichstaerke skaliert mit Aufloesung
    fscale = max(0.6, 0.9 * sc.s)         # Schriftgroesse

    frame_i = 0
    total_marks = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        blur = cv2.GaussianBlur(frame, (blur_k, blur_k), 0)
        diff = cv2.absdiff(blur, bg_blur)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, args.thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_k, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, dil_k, iterations=2)

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        n = 0
        for c in cnts:
            a = cv2.contourArea(c)
            if a < min_area or a > max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 235, 255), lw)
            n += 1
        total_marks += n
        cv2.putText(frame, f"bewegt: {n}", (12, round(30 * sc.s)),
                    cv2.FONT_HERSHEY_SIMPLEX, fscale, (0, 235, 255), lw)
        out.write(frame)
        frame_i += 1

    cap.release()
    out.release()
    print(f"Fertig: {frame_i} Frames, {total_marks} Markierungen gesamt "
          f"(~{total_marks/max(frame_i,1):.1f}/Frame) -> {args.dst}")


if __name__ == "__main__":
    main()
