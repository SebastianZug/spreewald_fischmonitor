# Fischzähler

Erkennung und Zählung von Fischen in Unterwasser-Videoaufnahmen einer
**stillstehenden** 360°-Kamera (Insta360). Zwei Kommandozeilen-Werkzeuge:

| Befehl        | Aufgabe                                                                 |
|---------------|------------------------------------------------------------------------|
| `fisch-detect`| markiert bewegte Objekte Frame für Frame (Hintergrund-Subtraktion)     |
| `fisch-track` | verfolgt Objekte über Frames, zählt eindeutige Fische, Zeit-Histogramm |

Zusätzlich liegt im Ordner [`site/`](site/) ein 360°-Video-Viewer (A-Frame)
für GitHub Pages samt `make_clip.sh` zum Schneiden/Stitchen der Rohaufnahmen.

## Voraussetzungen

* [uv](https://docs.astral.sh/uv/) (Paket- und venv-Manager, Windows + Linux)
* `ffmpeg` im Pfad – nur für `site/make_clip.sh` bzw. das Aufbereiten der
  Insta360-Rohdaten. Für `fisch-detect`/`fisch-track` selbst **nicht** nötig.

## Installation

```bash
uv sync
```

Das legt eine virtuelle Umgebung unter `.venv/` an und installiert alle
Abhängigkeiten (OpenCV, NumPy). Läuft unter Windows (PowerShell) und Linux
identisch.

## Nutzung

```bash
# Bewegte Objekte markieren:
uv run fisch-detect site/clips/demo.mp4 demo_marked.mp4

# Fische verfolgen und zählen (nur zählen, kein Video – schnell):
uv run fisch-track site/clips/demo.mp4 out.mp4 --count-only

# Mit Videoausgabe und angepassten Parametern:
uv run fisch-track site/clips/pos2_080712.mp4 tracked.mp4 --min 40 --move 30
```

Alle Parameter zeigt `uv run fisch-track --help` bzw. `uv run fisch-detect --help`.

Der Ansatz beruht darauf, dass die Kamera fest steht: der zeitliche Median
vieler Frames ergibt die Szene *ohne* Fische; alles, was sich davon abhebt und
in eine plausible Größe fällt, wird als bewegtes Objekt markiert.

## Entwicklung

```bash
uv sync --extra dev
uv run pytest
```

> Hinweis: Ist auf dem System ROS o. Ä. aktiv (setzt `PYTHONPATH`), kann das
> in die venv leaken und pytest-Plugins stören. Dann:
> `env -u PYTHONPATH uv run pytest` (nur Linux mit gesourctem ROS relevant).

## Projektstruktur

```
fischzähler/
├── pyproject.toml            # Projekt- und Abhängigkeitsdefinition (uv)
├── src/fischzaehler/
│   ├── background.py         # gemeinsamer Median-Hintergrund
│   ├── detect.py             # fisch-detect
│   └── track.py              # fisch-track
├── tests/                    # pytest
└── site/                     # 360°-Viewer für GitHub Pages + make_clip.sh
```

Die Rohdateien (`.lrv`, `.insv`, das MediaSDK, `.zip`) gehören **nicht** ins
Repo – sie sind zu groß für GitHub (Limit 100 MB pro Datei) und werden über
`.gitignore` ausgeschlossen.
