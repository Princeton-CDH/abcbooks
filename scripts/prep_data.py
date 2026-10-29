#!/usr/bin/env python
"""Prepare data files for the classify notebook.

Reads original data files from an input directory and writes cleaned
CSV files (image metadata, normalized and deduplicated tags, pages with an
image in the dataset).

Expected input files (in the input directory):
  - image_metadata.csv
  - tags.csv (tab-separated)
  - pages_with_canvases.csv (tab-separated)
  - abc_books_subset.h5

Usage:
  python scripts/prep_data.py content/data
  python scripts/prep_data.py originals/ -o content/data
"""

import argparse
import sys
from pathlib import Path

import h5py
import polars as pl

# default input files
IMAGE_METADATA = "image_metadata.csv"
TAGS = "tags.csv"
PAGES = "pages_with_canvases.csv"
DATASET = "abc_books_subset.h5"

OUTPUT_DIR = Path("public/data")


def prep_image_metadata(input_dir: Path, output_dir: Path) -> None:
    """Trim image metadata to the needed columns."""
    df = pl.read_csv(input_dir / IMAGE_METADATA, ignore_errors=True).select(
        "id", "image_iiif_id"
    )
    output_filename = "images.csv"
    df.write_csv(output_dir / output_filename)
    print(f"{output_filename}: {df.height:,} rows")


def prep_tags(input_dir: Path, output_dir: Path) -> pl.DataFrame:
    """Normalize tags (strip whitespace, lowercase), drop empty tags,
    and deduplicate."""
    df = (
        pl.read_csv(input_dir / TAGS, separator="\t")
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


def dataset_canvas_ids(input_dir: Path) -> pl.DataFrame:
    """Canvas ids for images in the dataset: image filename without extension
    (path is book ARK / canvas id .jpg)."""
    with h5py.File(input_dir / DATASET) as f:
        paths = f["image/paths"][:]
    return pl.DataFrame(
        {
            "canvas_id": [
                p.decode().rsplit("/", 1)[-1].removesuffix(".jpg") for p in paths
            ]
        }
    )


def prep_pages(input_dir: Path, output_dir: Path, tags: pl.DataFrame) -> None:
    """Subset pages to those with an image in the dataset. Untagged pages are
    kept so the notebook can predict tags for them."""
    df = (
        pl.read_csv(input_dir / PAGES, separator="\t")
        .rename(str.lower)
        .with_columns(canvas_id=pl.col.canvas.str.split("/").list.last())
        .join(dataset_canvas_ids(input_dir), on="canvas_id", how="semi")
        .sort("page_id")
    )
    df.write_csv(output_dir / "pages.csv")
    n_tagged = df.join(tags, on="page_id", how="semi").height
    print(f"pages.csv: {df.height:,} rows ({n_tagged:,} tagged)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "input_dir", type=Path, help="Directory containing original data files"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for output CSV files (default: %(default)s)",
    )
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    missing = [
        name
        for name in (IMAGE_METADATA, TAGS, PAGES, DATASET)
        if not (input_dir / name).exists()
    ]
    if missing:
        sys.exit(f"Missing input files in {input_dir}: {', '.join(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    prep_image_metadata(input_dir, output_dir)
    tags = prep_tags(input_dir, output_dir)
    prep_pages(input_dir, output_dir, tags)


if __name__ == "__main__":
    main()
