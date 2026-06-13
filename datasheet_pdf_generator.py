#!/usr/bin/env python3
"""
Wahapedia Datasheet PDF Printer
====================================
Erstellt ein PDF mit jeweils zwei Wahapedia-Datasheets pro DIN A4 Seite.
Alle Datasheets werden auf die *gleiche physische Größe* skaliert (konsistente Breite),
sodass alle gedruckten Karten gleich groß sind – ideal für Fotopapier-Ausdrucke in hoher Qualität.

Voraussetzungen:
- Google Chrome (für Headless-Rendering)
- Python-Pakete: Pillow, reportlab, numpy (meist vorhanden oder per pip install)
- Die 4 CSS-Dateien (fonts16.css, header16.css, main16.css, profile16.css) müssen
  im gleichen Ordner wie die HTML-Dateien liegen (oder im CSS-Ordner).

Nutzung:
    python3 datasheet_pdf_generator.py Rubric-Marines.html Thunderwolf-Cavalry.html
    python3 datasheet_pdf_generator.py --input-dir ./path_to_my_datasheets --target-width-mm 200 --margin-mm 4 --gap-mm 4
    python3 datasheet_pdf_generator.py --input-dir ./path_to_my_datasheets --output army_book.pdf --target-width-mm 200 --margin-mm 4 --gap-mm 4

Die HTML-Dateien sollten die von wahapedia_datasheet_printer.py erzeugten Dateien sein
(mit den passenden CSS-Links).
"""

import argparse
import subprocess
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def find_chrome_binary() -> str:
    """Sucht nach einem verfügbaren Chrome/Chromium-Binary auf Linux/macOS/Windows."""
    # 1. Umgebungsvariable hat höchste Priorität
    env_bin = os.environ.get("CHROME_BIN") or os.environ.get("GOOGLE_CHROME_BIN")
    if env_bin and Path(env_bin).exists():
        return env_bin

    # 2. Häufige Namen via which
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "google-chrome-beta",
        "chromium",
        "chromium-browser",
        "google-chrome-unstable",
    ]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path

    # 3. Häufige absolute Pfade (Linux)
    common_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/snap/bin/google-chrome",
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome-beta/google-chrome",
        "/usr/local/bin/google-chrome",
    ]
    for p in common_paths:
        if Path(p).exists():
            return p

    return ""


def render_html_to_png(
    html_path: Path,
    css_dir: Path,
    output_png: Path,
    chrome_binary: str,
    window_width: int = 2400,
    window_height: int = 4000,
    timeout: int = 90
) -> bool:
    """Rendert eine HTML-Datei mit Chrome Headless zu einem hochauflösenden PNG."""
    if not chrome_binary:
        print("[ERROR] Kein Chrome-Binary übergeben.")
        return False

    with tempfile.TemporaryDirectory(prefix="wahaprint_") as tmp:
        tmp_path = Path(tmp)
        # HTML und CSS-Dateien in temp kopieren (damit relative Pfade funktionieren)
        shutil.copy2(html_path, tmp_path / html_path.name)
        for css_name in ["fonts16.css", "header16.css", "main16.css", "profile16.css"]:
            src_css = css_dir / css_name
            if src_css.exists():
                shutil.copy2(src_css, tmp_path / css_name)
            else:
                # Fallback: im selben Ordner wie HTML suchen
                src_css2 = html_path.parent / css_name
                if src_css2.exists():
                    shutil.copy2(src_css2, tmp_path / css_name)

        html_file = tmp_path / html_path.name
        cmd = [
            chrome_binary,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-default-apps",
            "--no-first-run",
            f"--window-size={window_width},{window_height}",
            f"--screenshot={output_png.absolute()}",
            f"file://{html_file.absolute()}"
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0 and "written to file" not in (result.stderr or ""):
                print(f"[WARN] Chrome Rückgabewert {result.returncode} für {html_path.name}")
                if result.stderr:
                    print(result.stderr[-800:])
        except subprocess.TimeoutExpired:
            print(f"[ERROR] Timeout beim Rendern von {html_path.name}")
            return False

    return output_png.exists() and output_png.stat().st_size > 10000


def auto_crop_to_content(input_png: Path, output_png: Path, padding: int = 12) -> Optional[Tuple[int, int]]:
    """Schneidet das Bild auf den eigentlichen Inhalt zu (entfernt großen leeren Rand)."""
    try:
        img = Image.open(input_png).convert("RGB")
    except Exception as e:
        print(f"[ERROR] Kann Bild nicht öffnen: {e}")
        return None

    arr = np.array(img)
    # Inhalt = alles, was deutlich dunkler als fast-weiß ist
    mask = np.any(arr < 242, axis=2)
    if not mask.any():
        shutil.copy2(input_png, output_png)
        return img.size

    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # Padding hinzufügen und begrenzen
    rmin = max(0, rmin - padding)
    rmax = min(img.height - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(img.width - 1, cmax + padding)

    cropped = img.crop((cmin, rmin, cmax + 1, rmax + 1))
    cropped.save(output_png, "PNG", optimize=True)
    return cropped.size


def find_max_target_width(
    aspects: List[float],
    pair_indices: List[Tuple[int, Optional[int]]],
    gap_mm: float = 8.0,
    margin_mm: float = 12.0,
    max_try: float = 155.0,
    min_try: float = 105.0,
    step: float = 1.0
) -> float:
    """Ermittelt die größte Breite (mm), bei der alle Paare auf eine A4-Seite passen."""
    page_h_mm = 297.0
    avail_h_mm = page_h_mm - 2 * margin_mm

    best_w = min_try
    w = max_try
    while w >= min_try:
        fits_all = True
        for idx1, idx2 in pair_indices:
            h1 = aspects[idx1] * w
            h2 = aspects[idx2] * w if idx2 is not None else 0.0
            total_h = h1 + h2 + (gap_mm if idx2 is not None else 0.0)
            if total_h > avail_h_mm:
                fits_all = False
                break
        if fits_all:
            best_w = w
            break  # größter Wert gefunden (da absteigend)
        w -= step

    return round(best_w, 1)


def create_2up_pdf(
    png_pairs: List[Tuple[Path, Optional[Path]]],
    output_pdf: Path,
    target_width_mm: float,
    gap_mm: float = 8.0,
    margin_mm: float = 12.0,
    title: str = "Wahapedia Datasheets"
):
    """Erstellt das finale 2-up PDF mit konsistenter Skalierung."""
    page_w_pt, page_h_pt = A4
    target_w_pt = target_width_mm * mm
    left_x = (page_w_pt - target_w_pt) / 2   # zentriert

    c = canvas.Canvas(str(output_pdf), pagesize=A4)
    c.setTitle(title)
    c.setAuthor("Wahapedia 2-up Printer")

    for page_num, (png_top, png_bottom) in enumerate(png_pairs, 1):
        if page_num > 1:
            c.showPage()

        # Oberes Datasheet
        img1 = Image.open(png_top)
        w1, h1 = img1.size
        aspect1 = h1 / float(w1)
        h1_pt = aspect1 * target_w_pt
        y1 = page_h_pt - margin_mm * mm - h1_pt

        c.drawImage(
            ImageReader(img1),
            left_x,
            y1,
            width=target_w_pt,
            height=h1_pt,
            preserveAspectRatio=True,
            mask='auto'
        )

        # Unteres Datasheet (falls vorhanden)
        if png_bottom:
            img2 = Image.open(png_bottom)
            w2, h2 = img2.size
            aspect2 = h2 / float(w2)
            h2_pt = aspect2 * target_w_pt
            y2 = y1 - gap_mm * mm - h2_pt

            if y2 < margin_mm * mm:
                print(f"[WARN] Seite {page_num}: Unteres Datasheet passt möglicherweise nicht perfekt (zu hoch).")

            c.drawImage(
                ImageReader(img2),
                left_x,
                y2,
                width=target_w_pt,
                height=h2_pt,
                preserveAspectRatio=True,
                mask='auto'
            )

        # Kleine Seitenzahl unten
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(page_w_pt / 2, 6 * mm, f"Seite {page_num}")

    c.save()
    print(f"\n✅ PDF erstellt: {output_pdf.resolve()}")
    print(f"   Jede Karte hat eine Breite von {target_width_mm} mm auf dem Papier (konsistent).")


def main():
    parser = argparse.ArgumentParser(
        description="Erstellt PDF mit 2 Wahapedia-Datasheets pro A4-Seite in konsistenter Größe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python3 datasheet_pdf_generator.py Rubric-Marines.html Thunderwolf-Cavalry.html
  python3 datasheet_pdf_generator.py --input-dir ./path_to_my_datasheets --target-width-mm 200 --margin-mm 4 --gap-mm 4
  python3 datasheet_pdf_generator.py --input-dir ./path_to_my_datasheets --output army_book.pdf --target-width-mm 200 --margin-mm 4 --gap-mm 4
"""
    )
    parser.add_argument("html_files", nargs="*", help="Eine oder mehrere HTML-Dateien (in Verarbeitungsreihenfolge)")
    parser.add_argument("--input-dir", type=Path, help="Ordner mit vielen .html Dateien (werden alphabetisch sortiert)")
    parser.add_argument("--output", "-o", type=Path, default=Path("wahapedia_datasheets_2up.pdf"),
                        help="Ausgabe-PDF-Datei (Standard: wahapedia_datasheets_2up.pdf)")
    parser.add_argument("--target-width-mm", type=float, default=142.0,
                        help="Gewünschte Breite jeder Karte in mm (Standard: 142). Bei --auto-maximize Startwert.")
    parser.add_argument("--auto-maximize", action="store_true",
                        help="Automatisch die größtmögliche Breite ermitteln, bei der alle Paare auf eine Seite passen.")
    parser.add_argument("--gap-mm", type=float, default=7.0, help="Abstand zwischen den beiden Karten (mm)")
    parser.add_argument("--margin-mm", type=float, default=11.0, help="Rand oben/unten/links/rechts (mm)")
    parser.add_argument("--css-dir", type=Path, help="Ordner mit den CSS-Dateien (falls nicht neben den HTMLs)")
    parser.add_argument("--keep-temp", action="store_true", help="Temporäre Dateien nicht löschen (für Debug)")
    parser.add_argument("--force-rerender", action="store_true", help="Immer neu rendern (kein Cache)")

    args = parser.parse_args()

    # === Chrome Binary finden ===
    chrome_bin = find_chrome_binary()
    if not chrome_bin:
        print("[ERROR] Kein Google Chrome oder Chromium gefunden!")
        print("Bitte installiere eines der beiden:")
        print("  sudo apt update && sudo apt install chromium-browser")
        print("  # oder")
        print("  sudo apt install google-chrome-stable")
        print("\nAlternativ setze die Umgebungsvariable:")
        print("  export CHROME_BIN=/usr/bin/chromium")
        print("\nOder starte mit:")
        print("  CHROME_BIN=/pfad/zu/chrome python3 wahapedia_datasheet_2up.py ...")
        sys.exit(1)
    print(f"Verwende Browser: {chrome_bin}")

    # HTML-Dateien sammeln
    html_paths: List[Path] = []
    if args.input_dir:
        html_paths = sorted(args.input_dir.glob("*.html"))
        if not html_paths:
            print(f"[ERROR] Keine .html Dateien in {args.input_dir} gefunden.")
            sys.exit(1)
    elif args.html_files:
        html_paths = [Path(f) for f in args.html_files]
    else:
        print("[ERROR] Bitte HTML-Dateien angeben oder --input-dir verwenden.")
        parser.print_help()
        sys.exit(1)

    for hp in html_paths:
        if not hp.exists():
            print(f"[ERROR] Datei nicht gefunden: {hp}")
            sys.exit(1)

    css_dir = args.css_dir or html_paths[0].parent

    print(f"Verarbeite {len(html_paths)} Datasheet(s)...")
    print(f"CSS-Ordner: {css_dir}")

    work_dir = Path(tempfile.mkdtemp(prefix="wahaprint_work_"))
    print(f"Arbeitsverzeichnis: {work_dir}")

    rendered_pngs: List[Path] = []
    aspects: List[float] = []
    stems: List[str] = []

    for html_path in html_paths:
        stem = html_path.stem
        raw_png = work_dir / f"{stem}_raw.png"
        cropped_png = work_dir / f"{stem}_cropped.png"

        if cropped_png.exists() and not args.force_rerender:
            print(f"  [Cache] {stem}")
        else:
            print(f"  [Render] {stem} ...", end=" ", flush=True)
            ok = render_html_to_png(html_path, css_dir, raw_png, chrome_bin)
            if not ok:
                print("FEHLER beim Rendern!")
                continue
            size = auto_crop_to_content(raw_png, cropped_png)
            if size:
                print(f"OK ({size[0]}x{size[1]} px)")
            else:
                print("Crop fehlgeschlagen, verwende Original.")
                shutil.copy2(raw_png, cropped_png)

        # Aspect Ratio nach Crop
        try:
            with Image.open(cropped_png) as im:
                w, h = im.size
                aspects.append(h / float(w))
                rendered_pngs.append(cropped_png)
                stems.append(stem)
        except Exception as e:
            print(f"[ERROR] {stem}: {e}")

    if not rendered_pngs:
        print("[ERROR] Keine verwertbaren Datasheets gerendert.")
        sys.exit(1)

    # Paare bilden
    png_pairs: List[Tuple[Path, Optional[Path]]] = []
    pair_indices: List[Tuple[int, Optional[int]]] = []
    for j in range(0, len(rendered_pngs), 2):
        p1 = rendered_pngs[j]
        p2 = rendered_pngs[j + 1] if j + 1 < len(rendered_pngs) else None
        png_pairs.append((p1, p2))
        idx2 = j + 1 if j + 1 < len(rendered_pngs) else None
        pair_indices.append((j, idx2))

    # Zielbreite bestimmen
    if args.auto_maximize and len(png_pairs) > 0:
        target_w = find_max_target_width(
            aspects, pair_indices,
            gap_mm=args.gap_mm,
            margin_mm=args.margin_mm,
            max_try=min(args.target_width_mm + 15, 158),
            min_try=108
        )
        print(f"Auto-Maximize: {target_w} mm (größtmöglich für alle Paare)")
    else:
        target_w = args.target_width_mm
        print(f"Verwende feste Breite: {target_w} mm")

    # PDF erzeugen
    create_2up_pdf(
        png_pairs,
        args.output,
        target_width_mm=target_w,
        gap_mm=args.gap_mm,
        margin_mm=args.margin_mm,
        title=f"Wahapedia Datasheets – {len(rendered_pngs)} Einheiten"
    )

    if not args.keep_temp:
        shutil.rmtree(work_dir, ignore_errors=True)
        print("Temporäre Dateien gelöscht.")
    else:
        print(f"Temporäre Dateien bleiben erhalten unter: {work_dir}")


if __name__ == "__main__":
    main()
