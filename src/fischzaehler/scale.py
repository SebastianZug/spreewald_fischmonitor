"""Auflösungsbewusste Skalierung der Detektions-Parameter.

Die Default-Parameter (Blobflaeche, Suchradius, Netto-Weg, Kernelgroessen)
wurden auf einem 1664 px breiten equirectangular-Clip getunt. Bei hoeher
aufgeloestem Material belegt derselbe Fisch quadratisch mehr Pixel und wandert
linear mehr Pixel pro Frame. Damit dieselben Kommandozeilen-Werte bei jeder
Aufloesung dasselbe *physikalische* Objekt meinen, werden sie hier relativ zur
Referenzbreite umgerechnet.

Wichtig fuer kleine Fische: ein entfernter Fisch, der bei 1664 px unter der
Flaechenschwelle blieb, belegt bei 5760 px ~12x so viele Pixel und wird dadurch
ueberhaupt erst detektierbar. Deshalb wird die *Morphologie* bewusst nur
zurueckhaltend hochskaliert -- ein zu grosses MORPH_OPEN wuerde genau diese
kleinen, duennen Blobs wieder wegradieren.
"""
import math

#: Breite (px) des equirectangular-Clips, auf dem die Defaults getunt wurden.
REF_WIDTH = 1664


def odd(value):
    """Naechste ungerade Ganzzahl >= 1 (OpenCV-Kernel brauchen ungerade Groesse)."""
    n = max(1, int(round(value)))
    return n if n % 2 == 1 else n + 1


class Scaler:
    """Rechnet Referenz-Parameter (bei ``REF_WIDTH``) auf die Ist-Aufloesung um.

    * Laengen (Suchradius, Weg, Blur) skalieren linear mit ``s = width/ref``.
    * Flaechen (Blobgroesse) skalieren mit ``s**2``.
    * Die Morphologie-Kernel skalieren nur mit ``sqrt(s)`` -- gerade genug, um
      grobkoernigeres Rauschen bei hoher Aufloesung zu daempfen, ohne kleine
      Fische aufzufressen.
    """

    def __init__(self, width, ref_width=REF_WIDTH):
        self.width = width
        self.ref_width = ref_width
        self.s = width / ref_width
        self.area = self.s * self.s

    def length(self, ref_px):
        """Laenge/Distanz in Ziel-Pixeln."""
        return ref_px * self.s

    def area_px(self, ref_area):
        """Flaeche in Ziel-Pixeln^2."""
        return ref_area * self.area

    def blur_ksize(self, ref_k=5):
        """Ungerade Blur-Kernelgroesse, linear skaliert."""
        return odd(ref_k * self.s)

    def morph_ksize(self, ref_k=3):
        """Ungerade Morphologie-Kernelgroesse, nur mit sqrt(s) skaliert."""
        return odd(ref_k * math.sqrt(self.s))
