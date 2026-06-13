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

# === Fixed card size for uniform cutting ===
# Every generated card receives exactly this physical format (width x height in mm).
# The content is scaled via JavaScript so that it always fits into this box.
DEFAULT_CARD_WIDTH_MM = 200.0   # 20 cm
DEFAULT_CARD_HEIGHT_MM = 140.0  # 14 cm
CARD_RENDER_DPI = 300.0         # Resolution of the rendered box (for printing)
CARD_DESIGN_WIDTH_PX = 1100     # "Design width" of the datasheet (as in the original)


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
    Forces via inline styles + fallback that the lower KEYWORDS and
    FACTION KEYWORDS boxes have exactly the same column proportions as
    the main content above (62% left / remainder right). This makes all boxes
    flush with the right edge and visually consistent.
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
            # Only apply to likely keyword boxes (class or short content)
            # to avoid applying styles to parent frame containers that in some
            # datasheets cause an extra bottom border line.
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

    # Fallback: Also adjust children directly for .ds2col and .ds2colKW
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


def clean_html(
    html: str,
    page_title: str,
    card_width_mm: float = DEFAULT_CARD_WIDTH_MM,
    card_height_mm: float = DEFAULT_CARD_HEIGHT_MM,
) -> str:
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

    # Additional cleanup: Removes in some datasheets an unnecessary
    # empty or near-empty div at the bottom of dsOuterFrame that would
    # render an extra border/line below the actual frame.
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
            # Remove trailing near-empty divs that typically render extra border/line
            if len(txt) < 5 or (not txt and any(k in cls_lower for k in ["border", "line", "frame", "corner", "bottom", "dsfooter"])):
                if "border" in style or "height" in style or not txt:
                    child.decompose()
                    break

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else page_title

    # Calculate fixed card size in pixels (mm -> px at chosen DPI)
    px_per_mm = CARD_RENDER_DPI / 25.4
    card_w_px = int(round(card_width_mm * px_per_mm))
    card_h_px = int(round(card_height_mm * px_per_mm))

    # JS scales the datasheet content so it fits exactly into the fixed box.
    # Important: The box (black border) ALWAYS has the same size – regardless
    # of how much text is contained. This makes every card the same size.
    #
    # So that the content fills the ENTIRE box (without distortion), first
    # the layout width of the datasheet is chosen so that its rendered
    # aspect ratio (width/height) matches that of the box. Then it is
    # scaled with a uniform factor (zoom) -> fills width AND height,
    # proportions are preserved (no stretching).
    fit_script = """<script>
(function () {
  function fitCard() {
    var card = document.querySelector('.print-card');
    var content = document.querySelector('.print-container');
    if (!card || !content) { return; }

    // Always measure without scaling
    content.style.zoom = 1;

    var availW = card.clientWidth;
    var availH = card.clientHeight;
    if (availW <= 0 || availH <= 0) { return; }
    var targetRatio = availW / availH;

    // Search for the layout width where width/height of content == box ratio.
    // More width => text wraps wider => content becomes flatter => ratio increases.
    var lo = 600, hi = 4000;
    for (var i = 0; i < 32; i++) {
      var mid = (lo + hi) / 2;
      content.style.width = mid + 'px';
      var ratio = content.offsetWidth / content.offsetHeight;
      if (ratio < targetRatio) {
        lo = mid;   // still too tall -> make wider
      } else {
        hi = mid;   // wide enough -> try narrower again
      }
    }
    content.style.width = hi + 'px';

    var natW = content.offsetWidth;
    var natH = content.offsetHeight;
    if (natW <= 0 || natH <= 0) { return; }

    var scale = Math.min(availW / natW, availH / natH);
    content.style.zoom = scale;
  }
  if (document.readyState === 'complete') {
    fitCard();
  } else {
    window.addEventListener('load', fitCard);
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(fitCard);
  }
  setTimeout(fitCard, 300);
})();
</script>"""

    new_html = f"""<!DOCTYPE html>
<html lang="en">
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

        html, body {{
            background: #ffffff;
            font-family: 'ConduitITC', 'Minion Pro', Arial, sans-serif;
            padding: 0;
            margin: 0;
        }}

        /* Fixed card size ({card_width_mm:g} x {card_height_mm:g} mm).
           The black border is the cut line for trimming. */
        .print-card {{
            width: {card_w_px}px;
            height: {card_h_px}px;
            box-sizing: border-box;
            border: 2px solid #000;
            background: #ffffff;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
        }}

        .print-container {{
            width: {CARD_DESIGN_WIDTH_PX}px;
            margin: 0;
            background: white;
            box-sizing: border-box;
            padding: 20px;
        }}

        /* Remove icons top right */
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

        /* Flex layout for original proportions - main columns (Cyrillic class names from original CSS) */
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

        /* Flex layout for Keywords section - exactly same proportions + flush right */
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
    <div class="print-card">
        <div class="print-container">
            {str(main)}
        </div>
    </div>
    {fit_script}
</body>
</html>"""
    return new_html


def create_print_version(
    url: str,
    output_dir: str = "output",
    card_width_mm: float = DEFAULT_CARD_WIDTH_MM,
    card_height_mm: float = DEFAULT_CARD_HEIGHT_MM,
):
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

    print(f"📥 Loading and cleaning: {url}")
    html = fetch_datasheet(url)
    clean = clean_html(
        html,
        unit_slug.replace("-", " "),
        card_width_mm=card_width_mm,
        card_height_mm=card_height_mm,
    )

    html_path = Path(output_dir) / html_filename
    html_path.write_text(clean, encoding="utf-8")
    print(f"✅ Finished file: {html_path}")


def process_url_list(
    file_path: str,
    output_dir: str = "output",
    card_width_mm: float = DEFAULT_CARD_WIDTH_MM,
    card_height_mm: float = DEFAULT_CARD_HEIGHT_MM,
):
    """Process a .txt file with one URL per line."""
    try:
        with open(file_path, encoding="utf-8") as f:
            urls = []
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found.")
        return
    except Exception as e:
        print(f"❌ Error reading the file: {e}")
        return

    if not urls:
        print("⚠️  No valid URLs found in the file.")
        return

    total = len(urls)
    print(f"📋 Found {total} datasheet URLs. Starting processing...\n")

    # Copy CSS files only once at the beginning (saves time with many entries)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    script_dir = Path(__file__).parent
    for css in CSS_FILES:
        src = script_dir / css
        if not src.exists():
            src = script_dir / "attachments" / css
        if src.exists():
            shutil.copy(src, output_dir)

    for i, url in enumerate(urls, 1):
        print(f"[{i:3d}/{total}] 📥 {url}")
        try:
            create_print_version(
                url,
                output_dir,
                card_width_mm=card_width_mm,
                card_height_mm=card_height_mm,
            )
        except KeyboardInterrupt:
            print("\n⏹️  Aborted by user.")
            break
        except Exception as e:
            print(f"     ❌ Error: {e}\n")
        else:
            print()  # blank line for better readability


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Wahapedia Datasheet to print-ready HTML (single or list)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "url",
        nargs="?",
        help="Single URL, e.g. https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Rubric-Marines"
    )
    group.add_argument(
        "-f", "--file",
        metavar="FILE.txt",
        help="Text file with one URL per line (comments starting with # are ignored)"
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output folder (default: output)"
    )
    parser.add_argument(
        "--card-width-mm",
        type=float,
        default=DEFAULT_CARD_WIDTH_MM,
        help=f"Fixed card width in mm (default: {DEFAULT_CARD_WIDTH_MM:g})"
    )
    parser.add_argument(
        "--card-height-mm",
        type=float,
        default=DEFAULT_CARD_HEIGHT_MM,
        help=f"Fixed card height in mm (default: {DEFAULT_CARD_HEIGHT_MM:g})"
    )
    args = parser.parse_args()

    if args.file:
        process_url_list(
            args.file,
            args.output,
            card_width_mm=args.card_width_mm,
            card_height_mm=args.card_height_mm,
        )
    elif args.url:
        create_print_version(
            args.url,
            args.output,
            card_width_mm=args.card_width_mm,
            card_height_mm=args.card_height_mm,
        )
    else:
        parser.print_help()