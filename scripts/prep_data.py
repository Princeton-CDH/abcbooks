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
# local data from IIIF downloads and image dataset
BOOKS = "books.csv"
IIIF_PAGES = "pages.csv"
DATASET = "abcbooks.h5"

# exports from ABC Books class site (tab-separated)
TAGS = "tags.csv"
SITE_PAGES = "pages_with_canvases.csv"
SITE_BOOKS = "books.csv"

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
    print(
        f"✅ {dataset.name} is valid: {img_dataset.image_count:,} images with embeddings for default model"
    )


def prep_tags(site_dir: Path, output_dir: Path, pages: pl.DataFrame) -> None:
    """Normalize tags (strip whitespace, lowercase), drop empty tags,
    deduplicate, and limit to pages in the downloaded data."""
    tag_df = (
        pl.read_csv(site_dir / TAGS, separator="\t")
        .with_columns(tag=pl.col.tag.str.strip_chars().str.to_lowercase())
        .filter(pl.col.tag.is_not_null() & (pl.col.tag != ""))
        .unique()
        # use same page id column name as pages file
        .rename({"post_id": "page_id"})
        .sort("page_id", "tag")
    )
    # limit to pages with data
    tag_df = tag_df.join(pages.select("page_id"), on="page_id", how="inner")

    output_filename = "page_tags.csv"
    tag_df.write_csv(output_dir / output_filename)
    print(
        f"Tags: {tag_df.height:,} unique tag-page pairs. {tag_df['page_id'].n_unique():,} pages, {tag_df['tag'].n_unique():,} unique tags (-> saved to {output_filename})"
    )


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


def prep_pages(download_dir: Path, site_dir: Path, output_dir: Path) -> pl.DataFrame:
    """Combine site page export (page id, title, page number) with IIIF page
    metadata (book ARK, canvas label, image id), joined on canvas id; subset to
    pages with an image in the dataset and at least one tag."""
    # load data for downloaded page images
    pages_df = pl.read_csv(
        download_dir / IIIF_PAGES,
        schema_overrides={
            "label": pl.String  # override so polars doesn't wrongly infer as numeric
        },
    )
    if pages_df.height != pages_df.select("canvas_id").unique().height:
        print(
            f"Warning: {download_dir / IIIF_PAGES} has {pages_df.height - pages_df.select('canvas_id').unique().height:,} duplicate canvas ids"
        )
        # filter to unique set
        pages_df = pages_df.unique("canvas_id", keep="last")

    # one set of pages that is not in ABC Books class site has image filenames for labels; clean those up
    pages_df = pages_df.with_columns(
        label=pl.when(pl.col.label.str.contains(r"\.tif$", literal=False))
        .then(
            # remove .tif extension and leading zeros from label when it is an image filename
            pl.col.label.str.replace(
                r"\.tif$", "", literal=False
            ).str.strip_chars_start("0")
        )
        .otherwise(pl.col.label)
    )

    # load abcbook page-level data, so we can match images to site page ids - needed for associating with tags
    site_pages = (
        pl.read_csv(site_dir / SITE_PAGES, separator="\t")
        .rename(str.lower)
        # extract canvas id for joining with iiif pages
        .with_columns(canvas_id=pl.col.canvas.str.split("/").list.last())
        # book_id (ARK) comes from IIIF pages; site book id is added to books
        .select("page_id", "canvas_id", "title", "pagenum")
    )
    # join with site data to get page id, title, and page number for each canvas; keep all pages in download even if not in site data
    pages_df = pages_df.join(site_pages, on="canvas_id", how="left")

    pages_df.write_csv(output_dir / IIIF_PAGES)
    print(
        f"Pages: {pages_df.height:,} pages from {pages_df['book_id'].n_unique():,} books"
    )
    return pages_df


def prep_books(download_dir: Path, site_dir: Path, output_dir: Path) -> None:
    """Subset books to those with pages in the prepared pages data, and add
    the class site's numeric book id (for linking to the site), matched on
    IIIF manifest URL."""
    # load data for books included in the data downloads; only include books with pages (i.e., not multivolume works with sub-manifests)
    books_df = pl.read_csv(download_dir / BOOKS).filter(pl.col.page_count > 0)
    if books_df.height != books_df.select("book_id").unique().height:
        print(
            f"Warning: {BOOKS} has {books_df.height - books_df.select('book_id').unique().height:,} duplicate book ids"
        )
        # filter to unique set
        books_df = books_df.unique("book_id", keep="last")

    # site book data no longer adds anything, since we don't have an id for site urls
    # check that all books in the downloads are present in the site books data and warn if there is a mismatch

    site_books = (
        pl.read_csv(site_dir / SITE_BOOKS, separator="\t")
        .select(
            # site_book_id="BOOK_ID",  # numeric id no longer used for site urls; add slug if we get an export that includes it
            # site manifest URLs include an auth token; remove it so we can match on URLs
            manifest_url=pl.col.MANIFEST.str.replace(r"\?.*$", ""),
        )
        .unique()
    )
    # check for any downloaded books that are not in the site export; warn if any are found
    not_site_df = books_df.join(
        site_books, left_on="manifest_url", right_on="manifest_url", how="anti"
    )
    if not_site_df.height:
        print(
            f"⚠️ Warning: {not_site_df.height:,} books in {download_dir / BOOKS} not found in {site_dir / SITE_BOOKS}"
        )
        for row in not_site_df.iter_rows(named=True):
            truncated_title = (
                row["title"][:40] + "..." if len(row["title"]) > 40 else row["title"]
            )
            # fill to 43 characters for alignment (40 + 3 for ellipsis)
            truncated_title = truncated_title.ljust(43)
            print(f"  {truncated_title} {row['manifest_url']}")

    # report how many books in the site class data are in the download
    # the downloaded data is a subset of the site data, since we only use openly accessible volumes; report the total and percentage
    print(
        f"Downloaded data includes {books_df.height:,} books ({books_df.height / site_books.height:.1%} of ABC Books site {site_books.height:,} books)"
    )

    # check licenses for any that are not in the expected set:
    # - make sure we are only using openly licensed works,
    # - make sure we are not missing any licenses images for display in the notebook
    expected_licenses = [
        "https://creativecommons.org/publicdomain/mark/1.0/",
        "http://rightsstatements.org/vocab/NKC/1.0/",
        "http://rightsstatements.org/vocab/CNE/1.0/",
    ]
    # NOTE: this list can be expanded if there are other open licenses; if it changes, update the list in the notebook and add the image to assets/images/rights for display
    unexpected_licenses = books_df.filter(~pl.col.license.is_in(expected_licenses))
    if unexpected_licenses.height:
        print(
            f"⚠️ Warning: {unexpected_licenses.height:,} books have unexpected licenses:"
        )
        for row in unexpected_licenses.iter_rows(named=True):
            print(f"  {row['book_id']}: {row['license']}")

    # manifest is needed for joining but not needed for classify notebook, so drop before saving
    books_df = books_df.drop("manifest_url")
    books_df.write_csv(output_dir / BOOKS)


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
    prep_books(args.download_dir, args.site_dir, args.output_dir)
    pages_df = prep_pages(args.download_dir, args.site_dir, args.output_dir)
    prep_tags(args.site_dir, args.output_dir, pages_df)
    # copy_dataset from local data to notebook public data directory
    shutil.copy2(args.download_dir / DATASET, args.output_dir / DATASET)


if __name__ == "__main__":
    main()
