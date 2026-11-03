# ABC Books image classifier

## Local development

Use `uv` to install dependencies and run the [marimo](https://marimo.io/) notebook.

```bash
uv sync --dev
uv run marimo edit classify.py
```

To test or debug the HTML+WASM export locally, export in edit mode and serve:

```bash
uv run marimo export html-wasm --mode edit classify.py -o test/index.html
python -m http.server --directory test
```

This project uses a simplified branching pattern (no `develop` branch or tagged releases). If you would like to use git flow, install [git-flow-next](https://git-flow.sh/) and initialize it with the GitHub Flow branching pattern.

```bash
git flow init --preset=github
```

Before committing any changes to this repository, install [pre-commit](https://pre-commit.com/) and configured pre-commit hooks:

```bash
uv tool install pre-commit --with pre-commit-uv
pre-commit install
```

To update pre-commit hooks to latest versions, use:

```bash
pre-commit autoupdate --freeze
```

### Preparing data

A local copy of content from publicly-accessible materials in the [ABC Books](https://dpul.princeton.edu/cotsen/browse/abc-books) collection of Cotsen Children's Library is needed to generate the data used by the notebook. To download, run:

```bash
uv run scripts/download_images.py
```

This will download image files, organized by work ids, under `local_data/` and create two CSV files for the books and pages included in the download.

Then use iconoscope to create an image dataset from the downloaded images and generate at least two different embeddings. The notebook includes a dropdown to dynamically select from available embeddings.

```bash
iconoscope create local_data/images local_data/abcbooks.h5
iconoscope embed local_data/abcbooks.h5
iconoscope embed local_data/abcbooks.h5 --model siglip
```

Then use the data prep script to combine the downloaded data with exports from the ABC Books class site.

```bash
uv run scripts/prep_data.py abcbooks_exports_dir
```

This script expects a data containing the following files:

- `books.csv` - book metadata from the ABC Books site, including IIIF manifest for matching downloaded data
- `pages_with_canvases.csv` - page metadata ABC Books page ids and canvas URIs for matching downloaded data
- `tags.csv` - page-level tags from the ABC Books site

The script subsets, deduplicates, and combines source data files to create the input data needed for the notebook and put them in the `public/data/` folder, which are checked in and published with the notebook.

- `abcbooks.h5` - iconoscope image dataset with pre-computed embeddings
- `books.csv` - book metadata from IIIF manifests (ARK id, class site book id, title, manifest URL, license, page count); limited to books with pages in `pages.csv`
- `pages.csv` - page metadata exported from ABC Books site combined with IIIF page metadata (book ARK id, canvas id, label, IIIF image id), limited to image dataset subset
- `page_tags.csv` - page-level tags exported from ABC Books site, limited to image dataset subset

The script checks that the image dataset has embeddings for the
default model (as used by the notebook) and copies it to the output directory
along with the generated CSV files.

Output is written to `public/data/` unless `-o` is specified. The download and
output directories must differ, since they contain files with the same names.

### How the data is connected

Everything is joined on the **IIIF canvas id**. Each source stores it differently:

- **h5 paths:** the filename without `.jpg`, e.g.
  `ark--88435-08612z01r/133830a0-2007-4628-9867-c8f877ae59f5.jpg`
  → `133830a0-2007-4628-9867-c8f877ae59f5`. The folder is the book's ARK
  and isn't used.
- **`pages_with_canvases.csv`:** the last segment of the `CANVAS` URL.
- **`pages.csv`** (from `download_images.py`): the `canvas_id` column.

`tags.csv` joins to pages on `post_id` = `PAGE_ID`.

This assumes canvas ids (which are UUIDs) are unique across books.

### Content License images

CC license images can be downloaded from [Creative Commons](https://creativecommons.org/about/downloads/) and placed in `public/images/rights/` for use in the notebook and HTML export.
RightsStatements.org images can be downloaded from [Rights Statements assets](https://rightsstatements.org/en/documentation/assets.html); use the `dark-white-interior-blue-type` variant.

Images should be placed in `public/images/rights/` and given the prefix `cc-` or `rs-` to indicate the source. The notebook must be updated for any additional licenses.
