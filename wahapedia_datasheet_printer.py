#!/usr/bin/env python3
"""
Wahapedia Datasheet Printer
"""

import argparse
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

CSS_FILES = ["fonts16.css", "header16.css", "main16.css", "profile16.css"]

UNWANTED_SECTIONS = ["STRATAGEMS", "LED BY", "DETACHMENT ABILITY", "ENHANCEMENTS"]


def fetch_datasheet(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def remove_unwanted_sections(soup: BeautifulSoup) -> None:
    for header_text in UNWANTED_SECTIONS:
        for text_node in list(soup.find_all(string=True)):
            stripped = text_node.strip().upper()
            if stripped == header_text or stripped.startswith(header_text):
                container = text_node.parent
                climbs = 0
                while container and climbs < 5:
                    if container.name in ["div", "section", "article"] and len(list(container.children)) > 1:
                        break
                    if container.parent:
                        container = container.parent
                        climbs += 1
                    else:
                        break
                if container:
                    container.decompose()
                break

    for text_node in list(soup.find_all(string=True)):
        if "this unit can be led by" in text_node.lower():
            container = text_node.parent
            for _ in range(3):
                if container and container.name in ["div", "section", "p", "ul"]:
                    break
                if container and container.parent:
                    container = container.parent
            if container:
                container.decompose()


def remove_small_icons(main_content) -> None:
    for img in main_content.find_all("img"):
        try:
            w = int(img.get("width", 0))
            h = int(img.get("height", 0))
            if w < 45 or h < 45:
                img.decompose()
        except (ValueError, TypeError):
            src = img.get("src", "").lower()
            if any(x in src for x in ["icon", "arrow", "goto", "skull", "enlarge", "search"]):
                img.decompose()

    icon_classes = [
        "dsGoto", "enlarge_img", "picSearch", "picLegend",
        "dsCharSkull", "dsCharSkullInv", "altModels", "dsHeaderGoto"
    ]
    for cls in icon_classes:
        for el in main_content.find_all(class_=cls):
            el.decompose()


def clean_html(html: str, page_title: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for sel in [
        "script", "nav", ".NavWrapper", ".SiteHeader", ".NavUnderline",
        ".reAds", ".reAdsOverlay", ".btnContents", "#btnBackToTop",
        ".langSet", ".donate_buttons", ".yandex_search_line", ".datasheetsCollated"
    ]:
        for el in soup.select(sel):
            el.decompose()

    for p in soup.find_all("p"):
        if "does not meet the selection criteria" in p.get_text().lower():
            p.decompose()

    remove_unwanted_sections(soup)

    main = (
        soup.find("div", class_="dsOuterFrame")
        or soup.find("main")
        or soup.find("article")
        or soup.find("div", id="content")
        or soup.find("body")
    )
    if not main:
        main = soup

    remove_small_icons(main)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else page_title

    new_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>

    <link rel="stylesheet" href="fonts16.css">
    <link rel="stylesheet" href="header16.css">
    <link rel="stylesheet" href="main16.css">
    <link rel="stylesheet" href="profile16.css">

    <style>
        @media print {{
            @page {{ size: A4 portrait; margin: 8mm 10mm; }}
            body {{ background: white !important; color: black !important; print-color-adjust: exact !important; }}
            .print-container {{ box-shadow: none !important; padding: 0 !important; max-width: 100% !important; }}
            button, .NavWrapper, .reAds {{ display: none !important; }}
        }}

        body {{
            background: #f4f4f4;
            font-family: 'ConduitITC', 'Minion Pro', Arial, sans-serif;
            padding: 20px;
            margin: 0;
        }}

        .print-container {{
            max-width: 1100px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 25px rgba(0,0,0,0.15);
            padding: 25px;
        }}

        /* Icons oben rechts entfernen */
        .dsOuterFrame img,
        .dsBanner img,
        .dsHeader img,
        .dsProfileWrap img,
        .dsGoto,
        .enlarge_img,
        .picSearch,
        .picLegend,
        .dsCharSkull,
        .dsCharSkullInv,
        .altModels,
        .dsHeaderGoto {{
            display: none !important;
        }}

        /* Rechter Rand bündig */
        .dsOuterFrame,
        .dsBanner,
        .dsProfileBaseWrap,
        .dsProfileWrap,
        .ds2col,
        .dsLeftСol,
        .dsRightСol,
        .dsLeftСolKW,
        .dsRightСolKW,
        .two-col {{
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}

        .dsRightСol,
        .dsRightСolKW,
        .keywords-bar,
        .dsAbility,
        .section-header {{
            margin-right: 0 !important;
            padding-right: 0 !important;
            width: 100% !important;
        }}

        .keywords-bar {{
            width: 100% !important;
            box-sizing: border-box;
        }}
    </style>
</head>
<body>
    <div class="print-container">
        {str(main)}
    </div>
</body>
</html>"""
    return new_html


def create_print_version(url: str, output_dir: str = "output"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Dateiname aus letztem Teil der URL ableiten
    unit_slug = urlparse(url).path.rstrip("/").split("/")[-1]
    html_filename = f"{unit_slug}.html"

    script_dir = Path(__file__).parent
    for css in CSS_FILES:
        src = script_dir / css
        if not src.exists():
            src = script_dir / "attachments" / css
        if src.exists():
            shutil.copy(src, output_dir)

    print(f"📥 Lade und bereinige: {url}")
    html = fetch_datasheet(url)
    clean = clean_html(html, unit_slug.replace("-", " "))

    html_path = Path(output_dir) / html_filename
    html_path.write_text(clean, encoding="utf-8")
    print(f"✅ Fertige Datei: {html_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wahapedia Datasheet zu druckfertigem HTML konvertieren")
    parser.add_argument("url", help="z.B. https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Rubric-Marines")
    parser.add_argument("-o", "--output", default="output", help="Ausgabe-Ordner (Standard: output)")
    args = parser.parse_args()

    create_print_version(args.url, args.output)