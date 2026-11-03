#!/usr/bin/env python
"""Prepare data files for the classify notebook.

Reads data downloaded from IIIF and data exported from the ABC Books class
site, and writes cleaned CSV files (books, pages with image metadata,
normalized and deduplicated tags), limited to pages in the image dataset that
have at least one tag. The image dataset is checked for embeddings and copied
to the output directory along with the CSV files.

Expected input files:
  - download directory (default: local_data):
    books.csv, pages.csv (from scripts/download_images.py)
    abcbooks.h5 (iconoscope image dataset with embeddings)
  - site export directory (required), exported from the ABC Books site:
    books.csv, pages_with_canvases.csv, tags.csv (all tab-separated)

Usage:
  python scripts/prep_data.py site_exports/
  python scripts/prep_data.py site_exports/ -d local_data -o public/data
"""

import argparse
import shutil
import sys
from pathlib import Path

import polars as pl
from iconoscope.dataset import ImageDataset
from iconoscope.models import DEFAULT_MODEL, EmbeddingConfig

# input/output files
BOOKS = "books.csv"
IIIF_PAGES = "pages.csv"
TAGS = "tags.csv"
SITE_PAGES = "pages_with_canvases.csv"
SITE_BOOKS = "books.csv"
DATASET = "abcbooks.h5"

DOWNLOAD_DIR = Path("local_data")
OUTPUT_DIR = Path("public/data")


def check_dataset(dataset: Path) -> None:
    """Exit with an error if the image dataset is not valid or does not have
    embeddings for the default model (as used by the notebook)."""
    try:
        img_dataset = ImageDataset(dataset)
    except ValueError as err:
        sys.exit(f"Invalid image dataset: {err}")
    if not img_dataset.has_features(EmbeddingConfig(model=DEFAULT_MODEL)):
        sys.exit(
            f"Image dataset {dataset} has no embeddings for {DEFAULT_MODEL.name}; "
            f"run: iconoscope embed {dataset}"
        )
    print(f"{dataset.name}: {img_dataset.image_count:,} images with embeddings")


def prep_tags(site_dir: Path, output_dir: Path) -> pl.DataFrame:
    """Normalize tags (strip whitespace, lowercase), drop empty tags,
    and deduplicate."""
    df = (
        pl.read_csv(site_dir / TAGS, separator="\t")
        .with_columns(tag=pl.col.tag.str.strip_chars().str.to_lowercase())
        .filter(pl.col.tag.is_not_null() & (pl.col.tag != ""))
        .unique()
        # use same page id column name as pages file
        .rename({"post_id": "page_id"})
        .sort("page_id", "tag")
    )
    output_filename = "page_tags.csv"
    df.write_csv(output_dir / output_filename)
    print(f"{output_filename}: {df.height:,} rows")
    return df


def dataset_canvas_ids(dataset: Path) -> pl.DataFrame:
    """Canvas ids for images in the dataset: image filename without extension
    (path is book ARK / canvas id .jpg)."""
    return (
        # load the image dataset, get image data for dataframe of paths, extract canvas id
        ImageDataset(dataset)
        .get_image_data()
        .with_columns(
            canvas_id=pl.col.image_path.str.split("/")
            .list.last()
            .str.replace(".jpg$", "")
        )
    )


def prep_pages(
    download_dir: Path, site_dir: Path, output_dir: Path, tags: pl.DataFrame
) -> pl.DataFrame:
    """Combine site page export (page id, title, page number) with IIIF page
    metadata (book ARK, canvas label, image id), joined on canvas id; subset to
    pages with an image in the dataset and at least one tag."""
    site_pages = (
        pl.read_csv(site_dir / SITE_PAGES, separator="\t")
        .rename(str.lower)
        .with_columns(canvas_id=pl.col.canvas.str.split("/").list.last())
        # book_id (ARK) comes from IIIF pages; site book id is added to books
        .select("page_id", "canvas_id", "title", "pagenum")
    )
    df = (
        site_pages.join(
            pl.read_csv(
                download_dir / IIIF_PAGES, schema_overrides={"label": pl.String}
            ),
            on="canvas_id",
        )
        .join(dataset_canvas_ids(download_dir / DATASET), on="canvas_id", how="semi")
        .join(tags, on="page_id", how="semi")
        .unique("canvas_id")
        .sort("page_id")
    )
    df.write_csv(output_dir / IIIF_PAGES)
    print(f"{IIIF_PAGES}: {df.height:,} rows")
    return df


def prep_books(
    download_dir: Path, site_dir: Path, output_dir: Path, pages: pl.DataFrame
) -> None:
    """Subset books to those with pages in the prepared pages data, and add
    the class site's numeric book id (for linking to the site), matched on
    IIIF manifest URL."""
    site_books = pl.read_csv(site_dir / SITE_BOOKS, separator="\t").select(
        site_book_id="BOOK_ID",
        # site manifest URLs include an auth token; match on URL without it
        manifest_url=pl.col.MANIFEST.str.replace(r"\?.*$", ""),
    )
    df = (
        pl.read_csv(download_dir / BOOKS)
        .unique("book_id", keep="last")
        .join(pages, on="book_id", how="semi")
        .join(site_books, on="manifest_url", how="left")
        .select("book_id", "site_book_id", pl.exclude("book_id", "site_book_id"))
        .sort("book_id")
    )
    missing = df.filter(pl.col.site_book_id.is_null())
    if missing.height:
        print(
            f"Warning: no site book id for {missing.height} books: "
            f"{', '.join(missing['book_id'])}"
        )
    df.write_csv(output_dir / BOOKS)
    print(f"{BOOKS}: {df.height:,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "site_dir",
        type=Path,
        help=f"Directory with ABC Books site exports ({SITE_BOOKS}, {SITE_PAGES}, "
        f"{TAGS})",
    )
    parser.add_argument(
        "-d",
        "--download-dir",
        type=Path,
        default=DOWNLOAD_DIR,
        help=f"Directory with download_images.py output ({BOOKS}, {IIIF_PAGES}) "
        f"and image dataset ({DATASET}) (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for output data files (default: %(default)s)",
    )
    args = parser.parse_args()

    missing = [
        str(path)
        for path in (
            args.download_dir / BOOKS,
            args.download_dir / IIIF_PAGES,
            args.site_dir / SITE_BOOKS,
            args.site_dir / SITE_PAGES,
            args.site_dir / TAGS,
            args.download_dir / DATASET,
        )
        if not path.exists()
    ]
    if missing:
        sys.exit(f"Missing input files: {', '.join(missing)}")
    if args.download_dir.resolve() == args.output_dir.resolve():
        sys.exit("Download and output directories must differ")
    check_dataset(args.download_dir / DATASET)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tags = prep_tags(args.site_dir, args.output_dir)
    pages = prep_pages(args.download_dir, args.site_dir, args.output_dir, tags)
    prep_books(args.download_dir, args.site_dir, args.output_dir, pages)
    shutil.copy2(args.download_dir / DATASET, args.output_dir / DATASET)
    print(f"{DATASET}: copied to {args.output_dir}")


if __name__ == "__main__":
    main()
