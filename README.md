# Fischzähler

Erkennung und Zählung von Fischen in Unterwasser-Videoaufnahmen einer
**stillstehenden** 360°-Kamera (Insta360). Zwei Kommandozeilen-Werkzeuge:

| Befehl        | Aufgabe                                                                 |
|---------------|------------------------------------------------------------------------|
| `fisch-detect`| markiert bewegte Objekte Frame für Frame (Hintergrund-Subtraktion)     |
| `fisch-track` | verfolgt Objekte über Frames, zählt eindeutige Fische, Zeit-Histogramm |

Zusätzlich liegt im Ordner [`docs/`](docs/) ein 360°-Video-Viewer (A-Frame)
für GitHub Pages samt `make_clip.sh` zum Schneiden/Stitchen der Rohaufnahmen.

## Voraussetzungen

* [uv](https://docs.astral.sh/uv/) (Paket- und venv-Manager, Windows + Linux)
* `ffmpeg` im Pfad – nur für `docs/make_clip.sh` bzw. das Aufbereiten der
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
uv run fisch-detect docs/clips/demo.mp4 demo_marked.mp4

# Fische verfolgen und zählen (nur zählen, kein Video – schnell):
uv run fisch-track docs/clips/demo.mp4 out.mp4 --count-only

# Mit Videoausgabe und angepassten Parametern:
uv run fisch-track docs/clips/pos2_080712.mp4 tracked.mp4 --min 40 --move 30
```

Alle Parameter zeigt `uv run fisch-track --help` bzw. `uv run fisch-detect --help`.

Der Ansatz beruht darauf, dass die Kamera fest steht: der zeitliche Median
vieler Frames ergibt die Szene *ohne* Fische; alles, was sich davon abhebt und
in eine plausible Größe fällt, wird als bewegtes Objekt markiert.

### Höhere Auflösung & kleine Fische

Alle Größen-Parameter (`--min/--max`, `--max-dist`, `--move`) sind auf einen
1664 px breiten equirectangular-Clip getunt und werden **automatisch auf die
tatsächliche Videobreite hochskaliert** (Flächen quadratisch, Distanzen linear).
Dieselben Werte meinen so bei jeder Auflösung dasselbe *physikalische* Objekt.
Höher aufgelöstes Material (z. B. 5760 px aus der `.insv`) hilft, weil ein
entfernter Fisch dort mehr Pixel belegt und die Rauschschwelle überschreitet.
Mit `--ref-width` lässt sich die Bezugsbreite überschreiben.

### Pflanzenfilter (schwankende Vegetation)

Schwankende Wasserpflanzen bewegen sich zwar, aber **ortsfest**: derselbe Pixel
weicht in vielen Frames vom Hintergrund ab, während ein Fisch ihn nur kurz
aktiviert. `fisch-track` baut daraus in einem Vorlauf eine **Pflanzenmaske**
(Bewegungs-Häufigkeitskarte, `src/fischzaehler/activity.py`) und verwirft
Detektionen, die überwiegend darin liegen. Zusammen mit dem Netto-Weg-Filter
(`--move`) trennt das Fische von wiegendem Kraut. Steuerung:

```bash
fisch-track clip.mp4 out.mp4 --plant-persist 0.10   # Empfindlichkeit der Maske
fisch-track clip.mp4 out.mp4 --no-plant-mask        # Filter abschalten
```

### Klarere Darstellung (`--enhance`)

Unterwasseraufnahmen sind trüb und grünstichig. `--enhance` legt einen
kosmetischen Pass (Weißabgleich + CLAHE, `src/fischzaehler/enhance.py`) auf das
**Ausgabevideo** — bewusst *nach* der Detektion: auf den Erkennungs-Input gelegt
verstärkt CLAHE die Vegetationstextur und erzeugt massenhaft Fehlerkennungen
(empirisch geprüft). Die Detektion arbeitet daher weiter auf dem Rohbild, nur die
gezeigten Frames werden aufgehellt.

```bash
fisch-track clip.mp4 out.mp4 --enhance
```

### Szenen-Presets (`--preset`)

Verschiedene Aufnahmestellen brauchen verschiedene Parameter: das trübe Krautbett
(viele kleine Fische, wenig Blendung) verträgt niedrige Schwellen, die klare,
sonnige Fließ-Stelle (wenige große Fische, starke Kaustik/Partikel) braucht
höhere Mindestfläche und `--ignore-bright`. Diese Sets stehen in
[`presets.json`](presets.json) und werden per Namen geladen:

```bash
fisch-track pos2.mp4 out.mp4 --preset pos2_kraut --stats-json out.json
fisch-track pos1.mp4 out.mp4 --preset pos1_klar  --stats-json out.json
```

Auflösung der Werte: **explizites CLI-Argument > Preset > eingebauter Default**.
Ein Preset ist ein JSON-Objekt mit den Tuning-Schlüsseln (`min`, `thresh`,
`move`, `ignore_bright`, `plant_persist`, `enhance`, …). Mit `--presets-file`
lässt sich eine andere Datei angeben.

**Formfilter** (v. a. für klare Szenen mit driftenden Ästen): kompakte Fische
behalten, dünne/spindelige Objekte verwerfen — über die Kontur-Kennzahlen
`min_extent` (Fläche/Bounding-Box), `max_aspect` (Seitenverhältnis) und
`min_solidity` (Fläche/konvexe Hülle). Ein langer diagonaler Ast füllt seine
Box kaum (niedrige Extent, hohes Seitenverhältnis) und fliegt so raus, während
der kompakte Fisch bleibt. Jeweils `0` = aus (Default).

## Manuelle Einzel-Markierung (`fisch-mark`)

In klaren, sonnigen Szenen (starke Kaustik, Blendung, driftende Partikel)
scheitert die automatische Bewegungsdetektion — sie findet überall „Bewegung".
Ist aber nur **ein bekannter Fisch** interessant, gibt man ihn per Startbox vor;
ein Korrelationstracker (MIL) folgt ihm vorwärts **und** rückwärts durch den
Clip. Ergebnis: **genau eine rote Box „manuelle Identifikation"**, ohne jeden
Fehl-Treffer. Bewusst rot/beschriftet, um sie klar von der automatischen
Erkennung (grün = gezählt, gelb = beobachtet) zu unterscheiden.

```bash
# Startbox X Y B H auf den Fisch, Frame-Nr. der Startposition:
fisch-mark pos1.mp4 out.mp4 --seed 270 --box 2985 885 230 190 \
    --enhance --stats-json out.json
```

### Web-Viewer mit Zeitleiste

Der 360°-Viewer in [`docs/`](docs/) hat eine klick-/ziehbare Zeitleiste zum Vor-
und Zurückspringen. Darüber liegt eine **Fisch-Aktivitätsspur**: grün = Fische im
Zeitfenster (Helligkeit ~ Anzahl), dunkel = keine. Die Daten liefert
`--stats-json` (aktive Fische pro Frame), das der Viewer je Clip lädt:

```bash
# markiertes Video + passende Statistik in einem Lauf:
fisch-track clip.mp4 docs/clips/tracked.mp4 --enhance --stats-json docs/clips/tracked.json
```

In `docs/index.html` den Clip mit `stats`-Feld eintragen, dann zeigt die
Zeitleiste die Aktivitätsspur.

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
└── docs/                     # 360°-Viewer für GitHub Pages + make_clip.sh
```

Die Rohdateien (`.lrv`, `.insv`, das MediaSDK, `.zip`) gehören **nicht** ins
Repo – sie sind zu groß für GitHub (Limit 100 MB pro Datei) und werden über
`.gitignore` ausgeschlossen.
