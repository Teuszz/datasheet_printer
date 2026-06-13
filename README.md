# Wahapedia Datasheet Printer

A Python script that converts Warhammer 40,000 datasheets from [Wahapedia](https://wahapedia.ru) into clean, print-ready HTML files. Each datasheet is formatted as a fixed-size card (default: 200 × 140 mm / 20 × 14 cm) with a black border that serves as a precise cut line.

The content is automatically scaled via JavaScript to perfectly fill the card area while preserving aspect ratio — ideal for uniform printing and cutting for tabletop use.

## Features

- Fetches and cleans datasheet pages (removes navigation, ads, unwanted sections like Stratagems / "Led by", small icons, etc.)
- Aligns KEYWORDS and FACTION KEYWORDS boxes consistently with the main content columns
- Removes extra decorative elements that can appear on some datasheets
- **Fixed card size** — every card is exactly the same physical dimensions for easy batch printing/cutting
- Smart scaling: adjusts internal layout width first, then applies uniform zoom so content fills width *and* height without distortion or stretching
- Supports single URL or batch processing from a text file (one URL per line)
- Copies the required Wahapedia CSS files automatically
- Print-optimized: A4 portrait layout with minimal margins, black border as cut guide

## Requirements

- Python 3.8+
- `requests`
- `beautifulsoup4` (with `lxml` parser)

Install dependencies:

```bash
pip install requests beautifulsoup4
```

## Usage

### Single datasheet

```bash
python wahapedia_datasheet_printer.py "https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Rubric-Marines"
```

### Batch processing (recommended for armies)

Create a text file (e.g. `my_army.txt`) with one Wahapedia URL per line. Lines starting with `#` are treated as comments and ignored.

```bash
python wahapedia_datasheet_printer.py -f my_army.txt
```

### Command-line options

| Option                  | Description                                      | Default     |
|-------------------------|--------------------------------------------------|-------------|
| `-o`, `--output`        | Output directory                                 | `output`    |
| `--card-width-mm`       | Fixed card width in mm                           | `200`       |
| `--card-height-mm`      | Fixed card height in mm                          | `140`       |
| `-f`, `--file`          | Text file with URLs (one per line)               | —           |
| `url` (positional)      | Single datasheet URL                             | —           |

Example with custom card size (e.g. for smaller cards):

```bash
python wahapedia_datasheet_printer.py -f urls.txt --card-width-mm 180 --card-height-mm 120 -o my_cards/
```

## Output

For every processed URL you get:

- `unit-slug.html` — the ready-to-print datasheet card
- The four required CSS files (`fonts16.css`, `header16.css`, `main16.css`, `profile16.css`) are copied once into the output folder

Open any `.html` file in a browser → **Ctrl/Cmd + P** → Print.  
The page uses `@media print` rules so only the card appears, centered on A4 with the black border as your cut line.

## How the scaling works (technical note)

1. The outer `.print-card` div has a **fixed pixel size** calculated from the chosen mm dimensions at 300 DPI.
2. JavaScript measures the natural rendered size of the datasheet content.
3. It binary-searches for the optimal internal layout width so the content's aspect ratio exactly matches the target card ratio.
4. A single `zoom` factor is then applied so the content fills **both** width and height of the card perfectly (no letterboxing, no stretching).

This guarantees every card — regardless of how much text or how many wargear options it contains — has identical physical dimensions when printed.

## Notes & Tips

- Works with both English and localized Wahapedia pages.
- The black 2 px border is intended to be cut along — it disappears cleanly when trimmed.
- If a datasheet looks slightly off, try re-running with a slightly different `--card-width-mm` / `--card-height-mm` (the algorithm adapts automatically).
- For best print quality use "Fit to printable area" = Off / "Actual size" and high-quality paper/cardstock.

## License

This tool is provided as-is for personal, non-commercial use with Warhammer 40,000 datasheets from Wahapedia. Respect Games Workshop's and Wahapedia's terms of service.

Enjoy your perfectly uniform datasheet cards! ⚔️