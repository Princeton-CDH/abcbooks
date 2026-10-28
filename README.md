# ABC Books image classifier

## Local development

Use `uv` to install dependencies and run the [marimo](https://marimo.io/) notebook.

```bash
uv sync --dev
uv run marimo edit classify.py
```

To test or debug the HTML+WASM export locally, export in edit mode and serve:

```bash
uv run marimo export html-wasm classify.py -o test/index.html
python -m http.server --directory test
```

## Data

Data files needed for the notebook must be placed in `public/data/`.

- `abc_books_subset.h5` - iconoscope image dataset with pre-computed embeddings
- `images.csv` - image metadata to match image paths to metadata and iiif images
- `pages.csv` - page metadata exported from ABC Books site, limited to image dataset subset
- `page_tags.csv` - page-level tags exported from ABC Books site, limited to image dataset subset

### Preparing data

`scripts/prep_data.py` subsets, deduplicates, and converts source data files
into the above into input data needed for the notebook. Pass the directory containing the
originals; output is written to `public/data/` unless `-o` is specified:

```bash
uv run scripts/prep_data.py input_data_dir
```

It expects the following input files:

- `image_metadata.csv` : limit to `id` and `image_iiif_id` fields, save as `images.csv`
- `pages_with_canvases.csv`: limit to pages in the image dataset
- `tags.csv`: deduplicate, limit

### How the data is connected

Everything is joined on the **IIIF canvas id**. Each source stores it differently:

- **h5 paths:** the filename without `.jpg`, e.g.
  `ark--88435-08612z01r/133830a0-2007-4628-9867-c8f877ae59f5.jpg`
  → `133830a0-2007-4628-9867-c8f877ae59f5`. The folder is the book's ARK
  and isn't used.
- **`pages_with_canvases.csv`:** the last segment of the `CANVAS` URL.
- **`image_metadata.csv`:** the `id` column.

`tags.csv` joins to pages on `post_id` = `PAGE_ID`.

This assumes canvas ids (which are UUIDs) are unique across books.
