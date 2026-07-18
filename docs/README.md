# Fischzähler – 360°-Ausschnitte für GitHub Pages

Zeigt Ausschnitte der Insta360-Unterwasseraufnahmen als interaktives
360°-Video (A-Frame, Maus zum Umsehen) auf einer statischen Webseite.

## Aufbau

```
docs/
├── index.html      # die 360°-Viewer-Seite (A-Frame)
├── make_clip.sh    # Ausschnitte schneiden + stitchen + komprimieren
├── clips/          # die fertigen Web-Videos (kommen ins Repo)
└── README.md
```

Die Rohdateien (`.lrv`, `.insv`, das MediaSDK) gehören **nicht** ins Repo –
sie sind zu groß für GitHub (Limit 100 MB pro Datei).

## Neuen Ausschnitt hinzufügen

```bash
cd site
./make_clip.sh ../360_pos2/LRV_20260710_083428_01_011.lrv 00:03:00 20 baumstamm
```

Danach den Clip in `index.html` in der Liste `CLIPS` eintragen:

```js
const CLIPS = [
  { label: "Demo",       src: "clips/demo.mp4" },
  { label: "Baumstamm",  src: "clips/baumstamm.mp4" },
];
```

## Lokal ansehen

```bash
cd site
python3 -m http.server 8765
# dann http://localhost:8765/ im Browser öffnen
```

## Auf GitHub Pages veröffentlichen

1. Repo auf GitHub anlegen (z. B. `fischzaehler-360`).
2. Inhalt des Ordners `docs/` ins Repo pushen (Details im Chat).
3. In den Repo-Einstellungen: **Settings → Pages → Source = Branch `main`, Ordner `/ (root)`**.
4. Nach ~1 Minute erreichbar unter
   `https://<dein-name>.github.io/fischzaehler-360/`

## Hinweise

- **Dateigröße:** Ziel < 20–30 MB pro Clip, damit die Seite flüssig lädt.
  Kürzere Clips oder höheres `-crf` (z. B. 28) reduzieren die Größe.
- **Stitch-Naht:** Der ffmpeg-Weg ist eine Näherung. Perfekt wird die Naht
  nur mit dem Insta360-MediaSDK aus der Original-`.insv`.
- **Quelle:** Aktuell wird die niedrig aufgelöste `.lrv` (1664×832) genutzt.
  Mit der vollen `.insv` wäre das Ergebnis deutlich schärfer.
