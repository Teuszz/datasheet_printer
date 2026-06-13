# Wahapedia Datasheet Tools

A small suite of Python scripts for turning Warhammer 40,000 datasheets from [Wahapedia](https://wahapedia.ru) into beautiful, print-ready materials with **perfectly consistent physical sizes**.

The two tools work together as a complete workflow:

1. `wahapedia_datasheet_printer.py` — converts online datasheets into fixed-size HTML cards
2. `datasheet_pdf_generator.py` — turns those HTML cards into a 2-up PDF (two per A4 page) with uniform card widths

---

## Quickstart Workflow

1. Create virtual environment and install necessary Python packages:
    ```bash
    # 1. Create virtual environment
    python3 -m venv venv

    # 2. Activate virtual environment
    source venv/bin/activate          # Linux / macOS
    # venv\Scripts\activate           # Windows

    # 3. Install required Python packages
    pip install -r requirements.txt
    ```

2. Create a `my_army_urls.txt` file with each line containing an URL to a wahapedia datasheet
   you would like to print

3. Generate HTML cards for your whole army:
   ```bash
   python wahapedia_datasheet_printer.py -f my_army_urls.txt -o html_cards/ --card-width-mm 200 --card-height-mm 140
   ```

4. Create a beautiful PDF with maximum uniform card size:
   ```bash
   python datasheet_pdf_generator.py --input-dir html_cards/ \
       --target-width-mm 200
       --output my_army.pdf \
       --margin-mm 4 --gap-mm 4
   ```

5. Print the PDF on photo paper or cardstock at 100% scale and cut along the edges.

Enjoy your perfectly uniform, professional-looking datasheet cards! ⚔️

---

## 1. Wahapedia Datasheet Printer (`wahapedia_datasheet_printer.py`)

Converts Warhammer 40,000 datasheets from Wahapedia into clean, print-ready HTML files. Each datasheet is formatted as a fixed-size card (default: 200 × 140 mm) with a black border that serves as a precise cut line.

The content is automatically scaled via JavaScript to perfectly fill the card area while preserving aspect ratio — ideal for uniform printing and cutting for tabletop use.

### Features

- Fetches and cleans datasheet pages (removes navigation, ads, unwanted sections like Stratagems / "Led by", small icons, etc.)
- Aligns KEYWORDS and FACTION KEYWORDS boxes consistently with the main content columns
- Removes extra decorative elements that can appear on some datasheets
- **Fixed card size** — every card is exactly the same physical dimensions for easy batch printing/cutting
- Smart scaling: adjusts internal layout width first, then applies uniform zoom so content fills width *and* height without distortion or stretching
- Supports single URL or batch processing from a text file (one URL per line)
- Copies the required Wahapedia CSS files automatically
- Print-optimized: A4 portrait layout with minimal margins, black border as cut guide

### Requirements

- Python 3.8+
- `requests`
- `beautifulsoup4` (with `lxml` parser)

Install dependencies:

```bash
pip install requests beautifulsoup4
```

### Usage

#### Single datasheet

```bash
python wahapedia_datasheet_printer.py "https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Rubric-Marines"
```

#### Batch processing (recommended for armies)

Create a text file (e.g. `my_army.txt`) with one Wahapedia URL per line. Lines starting with `#` are treated as comments and ignored.

```bash
python wahapedia_datasheet_printer.py -f my_army.txt
```

#### Command-line options

| Option                  | Description                                      | Default     |
|-------------------------|--------------------------------------------------|-------------|
| `-o`, `--output`        | Output directory                                 | `output`    |
| `--card-width-mm`       | Fixed card width in mm                           | `200`       |
| `--card-height-mm`      | Fixed card height in mm                          | `140`       |
| `-f`, `--file`          | Text file with URLs (one per line)               | —           |
| `url` (positional)      | Single datasheet URL                             | —           |

Example with custom card size:

```bash
python wahapedia_datasheet_printer.py -f urls.txt --card-width-mm 180 --card-height-mm 120 -o my_cards/
```

### Output

For every processed URL you get:

- `unit-slug.html` — the ready-to-print datasheet card
- The four required CSS files (`fonts16.css`, `header16.css`, `main16.css`, `profile16.css`) are copied once into the output folder

Open any `.html` file in a browser → **Ctrl/Cmd + P** → Print.  
The page uses `@media print` rules so only the card appears, centered on A4 with the black border as your cut line.

### How the scaling works (technical note)

1. The outer `.print-card` div has a **fixed pixel size** calculated from the chosen mm dimensions at 300 DPI.
2. JavaScript measures the natural rendered size of the datasheet content.
3. It binary-searches for the optimal internal layout width so the content's aspect ratio exactly matches the target card ratio.
4. A single `zoom` factor is then applied so the content fills **both** width and height of the card perfectly (no letterboxing, no stretching).

This guarantees every card — regardless of how much text or how many wargear options it contains — has identical physical dimensions when printed.

### Notes & Tips

- Works with both English and localized Wahapedia pages.
- The black 2 px border is intended to be cut along — it disappears cleanly when trimmed.
- If a datasheet looks slightly off, try re-running with a slightly different `--card-width-mm` / `--card-height-mm` (the algorithm adapts automatically).
- For best print quality use "Fit to printable area" = Off / "Actual size" and high-quality paper/cardstock.

---

## 2. Wahapedia Datasheet PDF Generator (`datasheet_pdf_generator.py`)

Takes the HTML cards produced by the first script and creates a professional **2-up PDF** (two datasheets per A4 page) with **perfectly consistent physical card widths** across your entire army.

This is especially useful when you want to print many datasheets on photo paper or cardstock in one go. Every card on every page will have exactly the same width (you choose it, or let the script find the maximum that still fits).

The tool:
- Uses headless Google Chrome to render each HTML card to a high-resolution PNG
- Automatically crops away empty margins
- Calculates the optimal layout so that **all cards have identical width** on the printed page
- Optionally uses `--auto-maximize` to find the largest possible card width that still allows every pair to fit on one A4 page

### Features

- **Consistent physical size** — every datasheet card has exactly the same width on paper (no more "some cards bigger than others")
- 2-up layout (two cards per A4 page) with configurable gap and margins
- Smart auto-cropping of rendered images
- Optional automatic width maximization (finds the biggest cards that still fit all pairs)
- Page numbers at the bottom of each page
- Caching of rendered PNGs (re-renders only when needed or when `--force-rerender` is used)
- Works great with the fixed-size HTML cards from `wahapedia_datasheet_printer.py`

### Requirements

- Google Chrome or Chromium (headless rendering)
- Python packages: `Pillow`, `reportlab`, `numpy`

Install dependencies:

```bash
pip install Pillow reportlab numpy
```

### Usage

#### Basic usage (two specific files)

```bash
python datasheet_pdf_generator.py Rubric-Marines.html Thunderwolf-Cavalry.html
```

#### Process an entire folder (recommended)

```bash
python datasheet_pdf_generator.py --input-dir ./my_army_htmls/
```

#### With automatic maximum width + custom output name

```bash
python datasheet_pdf_generator.py --input-dir ./my_army_htmls/ \
    --auto-maximize \
    --output my_army_book.pdf \
    --target-width-mm 200 \
    --margin-mm 8 \
    --gap-mm 6
```

#### Command-line options

| Option                    | Description                                                                 | Default                          |
|---------------------------|-----------------------------------------------------------------------------|----------------------------------|
| `html_files`              | One or more HTML files (positional)                                         | —                                |
| `--input-dir`             | Folder with `.html` files (sorted alphabetically)                           | —                                |
| `--output`, `-o`          | Output PDF filename                                                         | `wahapedia_datasheets_2up.pdf`   |
| `--target-width-mm`       | Desired card width in mm (starting value for auto-maximize)                 | `142`                            |
| `--auto-maximize`         | Automatically find the largest width that lets all pairs fit on A4 pages    | off                              |
| `--gap-mm`                | Vertical gap between the two cards on a page (mm)                           | `7`                              |
| `--margin-mm`             | Margin on all four sides of the page (mm)                                   | `11`                             |
| `--css-dir`               | Folder containing the 4 CSS files (if not next to the HTML files)           | same folder as first HTML        |
| `--keep-temp`             | Keep temporary render files (useful for debugging)                          | off                              |
| `--force-rerender`        | Ignore cache and re-render every HTML file                                  | off                              |

### How consistent sizing works

1. Every HTML card is rendered at high resolution with Chrome.
2. The script measures the **aspect ratio** of each cropped card.
3. It then scales **all cards to the exact same target width** (in mm) on the PDF page.
4. When `--auto-maximize` is used, it binary-searches for the largest width where the summed heights of every pair (plus gap) still fit within the available A4 height minus margins.

Result: Every printed card has **identical physical width**, regardless of how tall or short its content is.

### Output

A single PDF file (e.g. `wahapedia_datasheets_2up.pdf`) containing all your datasheets laid out two per page, ready for high-quality printing.

Open the PDF and print with "Actual size" / 100% scaling for perfect dimensions.

### Tips

- Use `--auto-maximize` when you have many datasheets of varying lengths — it will give you the biggest possible uniform cards.
- The default `--target-width-mm 142` is a good balanced starting point for most armies.
- If a bottom card on a page gets slightly cut off, reduce `--target-width-mm` a little or increase `--margin-mm`.
- The four CSS files must be available (the script copies them into a temp folder automatically).

---

## License

These tools are provided as-is for personal, non-commercial use with Warhammer 40,000 datasheets from Wahapedia. Respect Games Workshop's and Wahapedia's terms of service.