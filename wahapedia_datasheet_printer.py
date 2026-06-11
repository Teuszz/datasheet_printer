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


def align_keyword_boxes(main_content: BeautifulSoup) -> None:
    """
    Erzwingt per Inline-Style + Fallback, dass die unteren KEYWORDS- und
    FACTION KEYWORDS-Boxen exakt dieselben Spaltenproportionen haben wie
    der Hauptinhalt oben (62 % links / Rest rechts). Dadurch sind alle Boxen
    bündig mit dem rechten Rand und visuell konsistent.
    """
    for text_node in list(main_content.find_all(string=True)):
        text_upper = text_node.strip().upper()
        if not (text_upper.startswith("KEYWORDS") or text_upper.startswith("FACTION KEYWORDS")):
            continue

        is_faction = text_upper.startswith("FACTION KEYWORDS")

        container = text_node.parent
        for _ in range(5):
            if container is None:
                break
            if container.name == "div":
                txt = container.get_text(" ", strip=True).upper()
                if "KEYWORDS" in txt and len(txt) < 600:
                    break
            container = getattr(container, "parent", None)

        if container and container.name == "div":
            # Nur auf wahrscheinliche Keyword-Boxen anwenden (Klasse oder kurzer Inhalt),
            # um zu vermeiden, dass Styles auf übergeordnete Frame-Container angewendet werden,
            # die bei manchen Datasheets den extra unteren Umrandungsstrich verursachen.
            classes = " ".join(container.get("class", [])).lower()
            txt_len = len(container.get_text(" ", strip=True))
            if "keyword" in classes or "kw" in classes or "col" in classes or txt_len < 800:
                if is_faction:
                    style_add = (
                        "flex: 1 1 auto !important; "
                        "width: auto !important; "
                        "max-width: 100% !important; "
                        "box-sizing: border-box !important; "
                        "padding-left: 8px !important;"
                    )
                else:
                    style_add = (
                        "flex: 0 0 62% !important; "
                        "width: 62% !important; "
                        "max-width: 62% !important; "
                        "box-sizing: border-box !important; "
                        "padding-right: 8px !important;"
                    )

                existing = container.get("style", "")
                container["style"] = (existing + "; " + style_add).strip("; ")

                parent = container.parent
                if parent and parent.name == "div":
                    p_style = parent.get("style", "")
                    if "flex" not in p_style.lower():
                        parent["style"] = (
                            p_style + "; display: flex !important; width: 100% !important; "
                            "gap: 0; align-items: flex-start; box-sizing: border-box !important;"
                        ).strip("; ")

    # Fallback: Auch bei .ds2col und .ds2colKW direkt die Kinder anpassen
    for col_class in ["ds2col", "ds2colKW"]:
        for ds2 in main_content.find_all(class_=col_class):
            if "KEYWORDS" in ds2.get_text().upper():
                children = [c for c in ds2.children if getattr(c, "name", None) == "div"]
                if len(children) == 2:
                    children[0]["style"] = (
                        children[0].get("style", "") +
                        "; flex: 0 0 62% !important; width: 62% !important; "
                        "max-width: 62% !important; box-sizing: border-box !important; padding-right: 8px !important;"
                    ).strip()
                    children[1]["style"] = (
                        children[1].get("style", "") +
                        "; flex: 1 1 auto !important; width: auto !important; "
                        "max-width: 100% !important; box-sizing: border-box !important; padding-left: 8px !important;"
                    ).strip()


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

    align_keyword_boxes(main)

    # Zusätzliche Bereinigung: Entfernt bei manchen Datasheets ein überflüssiges
    # leeres oder fast-leeres div am unteren Ende der dsOuterFrame, das einen
    # zusätzlichen Strich der Umrandung unterhalb des eigentlichen Rahmens erzeugt.
    # Dies tritt bei bestimmten Einheiten (z.B. T'au, Necrons, manche Orks) auf,
    # deren HTML-Struktur ein extra Rahmenelement am Ende enthält.
    outer = None
    if main and getattr(main, "name", None) == "div":
        classes = main.get("class", []) or []
        if any("dsOuterFrame" in str(c) for c in classes):
            outer = main
    if not outer and main:
        outer = main.find("div", class_="dsOuterFrame") if hasattr(main, "find") else None
    if outer:
        for child in reversed(list(outer.children)):
            if getattr(child, "name", None) != "div":
                continue
            txt = child.get_text(strip=True) if hasattr(child, "get_text") else ""
            classes_str = " ".join(child.get("class", [])) if hasattr(child, "get") else ""
            style = (child.get("style") or "").lower() if hasattr(child, "get") else ""
            cls_lower = classes_str.lower()
            # Entferne trailing near-empty divs die typischerweise extra border/line rendern
            if len(txt) < 5 or (not txt and any(k in cls_lower for k in ["border", "line", "frame", "corner", "bottom", "dsfooter"])):
                if "border" in style or "height" in style or not txt:
                    child.decompose()
                    break

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

        /* Flex-Layout für originale Proportionen - Hauptspalten (kyrillische Klassennamen aus Original-CSS) */
        .ds2col {{
            display: flex !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}

        .dsLeftСol {{
            flex: 0 0 62% !important;
            max-width: 62% !important;
            box-sizing: border-box !important;
        }}

        .dsRightСol {{
            flex: 1 1 auto !important;
            margin-right: 0 !important;
            padding-right: 0 !important;
            box-sizing: border-box !important;
        }}

        /* Flex-Layout für Keywords-Sektion - exakt gleiche Proportionen + bündig rechts */
        .ds2colKW {{
            display: flex !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            align-items: stretch !important;
        }}

        .dsLeftСolKW {{
            flex: 0 0 62% !important;
            max-width: 62% !important;
            box-sizing: border-box !important;
            padding-right: 8px !important;
        }}

        .dsRightСolKW {{
            flex: 1 1 auto !important;
            margin-right: 0 !important;
            padding-right: 0 !important;
            box-sizing: border-box !important;
            padding-left: 8px !important;
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