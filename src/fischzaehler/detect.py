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


def main():
    ap = argparse.ArgumentParser(prog="fisch-detect", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--min", type=int, default=60, help="min. Blobflaeche in px")
    ap.add_argument("--max", type=int, default=8000, help="max. Blobflaeche in px")
    ap.add_argument("--thresh", type=int, default=22, help="Diff-Schwelle 0-255")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.src)
    if not cap.isOpened():
        raise SystemExit(f"Konnte Video nicht oeffnen: {args.src}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    print(f"Video {w}x{h} @ {fps:.1f}fps – berechne Hintergrund ...")
    bg_blur = cv2.GaussianBlur(median_background(cap), (5, 5), 0)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.dst, fourcc, fps, (w, h))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    frame_i = 0
    total_marks = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        diff = cv2.absdiff(blur, bg_blur)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, args.thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=2)

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        n = 0
        for c in cnts:
            a = cv2.contourArea(c)
            if a < args.min or a > args.max:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 235, 255), 2)
            n += 1
        total_marks += n
        cv2.putText(frame, f"bewegt: {n}", (12, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 235, 255), 2)
        out.write(frame)
        frame_i += 1

    cap.release()
    out.release()
    print(f"Fertig: {frame_i} Frames, {total_marks} Markierungen gesamt "
          f"(~{total_marks/max(frame_i,1):.1f}/Frame) -> {args.dst}")


if __name__ == "__main__":
    main()
