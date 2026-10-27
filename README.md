# ABC Books image classifier

Built with [marimo-book](https://github.com/ljchang/marimo-book).

## Local development

```bash
uv sync --dev

# Live-reload dev server (browse at http://127.0.0.1:8000/)
marimo-book serve

# One-shot build (emits ./_site/)
marimo-book build

# Validate book.yml + content without building
marimo-book check

# Remove build artifacts
marimo-book clean
```

## Layout

- `book.yml` — TOC, theme, branding, launch-button config
- `content/` — your `.md` and marimo `.py` chapters
- `data/` — datasets used by the notebooks; copied as-is into the built site
  so WASM notebooks can fetch them
- `.github/workflows/deploy.yml` — builds and publishes to GitHub Pages
  on every push to `main` (edit or delete as needed)

## Data

`data/` contains:

| file | contents |
|---|---|
| `abc_books_subset.h5` | iconoscope export: image paths (`image/paths`) and DINOv2 embeddings (`image/models/dinov2/defaults/features`, 768 floats per image) |
| `pages_with_canvases.csv` | tab-separated; one row per tagged page: `PAGE_ID`, `TITLE`, `BOOK_ID`, `PAGENUM`, `CANVAS` (IIIF canvas URL) |
| `tags.csv` | tab-separated; one row per (page, tag): `post_id` (= `PAGE_ID`), `tag`. Contains duplicate rows; the notebook de-duplicates and lower-cases tags |
| `image_metadata.csv` | `id` (canvas id) and `image_iiif_id` (IIIF image URL). Only used to show page thumbnails |

### Preparing data

`scripts/prep_data.py` converts the original files above into the parquet
files used by the classify notebook. Pass the directory containing the
originals; output is written to the same directory unless `-o` is given:

```bash
uv run scripts/prep_data.py content/data
uv run scripts/prep_data.py path/to/originals -o content/data
```

It writes:

| file | contents |
|---|---|
| `image_metadata.parquet` | `image_metadata.csv` trimmed to `id` and `image_iiif_id` |
| `tags.parquet` | `tags.csv` with duplicate rows removed |
| `pages.parquet` | rows of `pages_with_canvases.csv` with an image in `abc_books_subset.h5` and at least one tag, plus a `canvas_id` column |

### How the files are joined

Everything is joined on the **IIIF canvas id**. Each source stores it differently:

- **h5 paths:** the filename without `.jpg`, e.g.
  `ark--88435-08612z01r/133830a0-2007-4628-9867-c8f877ae59f5.jpg`
  → `133830a0-2007-4628-9867-c8f877ae59f5`. The folder is the book's ARK
  and isn't used.
- **`pages_with_canvases.csv`:** the last segment of the `CANVAS` URL.
- **`image_metadata.csv`:** the `id` column.

`tags.csv` joins to pages on `post_id` = `PAGE_ID`.

This assumes canvas ids are unique across books. They're UUIDs, so this
should hold, but it hasn't been checked.

`image_metadata.csv` is trimmed to the two columns above. The original
export's `download_path` column isn't needed (the h5 paths already contain the
canvas id) and contains local paths. Don't publish `books.csv`: its manifest
URLs include an `auth_token`.
