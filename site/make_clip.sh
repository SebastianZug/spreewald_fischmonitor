#!/usr/bin/env bash
# Schneidet einen Ausschnitt aus einer Insta360-Dual-Fisheye-LRV/INSV,
# stitcht ihn zu equirectangular (360°) und komprimiert ihn fürs Web.
#
# Nutzung:
#   ./make_clip.sh <quelle> <start> <dauer> <ausgabename> [fov]
#
# Beispiel (ab Minute 3:00, 20 Sekunden lang):
#   ./make_clip.sh ../360_pos2/LRV_20260710_083428_01_011.lrv 00:03:00 20 baumstamm
#
#   -> erzeugt clips/baumstamm.mp4
#
# start  = Startzeitpunkt (Sekunden oder HH:MM:SS)
# dauer  = Länge in Sekunden
# fov    = optional, Objektiv-Blickwinkel (Default 200). Bei sichtbarer
#          Naht mit 190–210 experimentieren.
#
# roll=-90 dreht das Bild aufrecht (Kamera lag auf der Seite).

set -euo pipefail

SRC="${1:?Quelle fehlt}"
START="${2:?Start fehlt}"
DUR="${3:?Dauer fehlt}"
NAME="${4:?Ausgabename fehlt}"
FOV="${5:-200}"
ROLL="${6:--90}"

mkdir -p clips
OUT="clips/${NAME}.mp4"

ffmpeg -hide_banner -stats -loglevel error \
  -ss "$START" -i "$SRC" -t "$DUR" \
  -vf "v360=dfisheye:e:ih_fov=${FOV}:iv_fov=${FOV}:roll=${ROLL}" \
  -c:v libx264 -crf 26 -preset veryfast -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 96k \
  "$OUT" -y

echo
echo "Fertig: $OUT ($(du -h "$OUT" | cut -f1))"
echo "Jetzt in index.html unter CLIPS eintragen:"
echo "    { label: \"${NAME}\", src: \"clips/${NAME}.mp4\" },"
