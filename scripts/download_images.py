#!/usr/bin/env python
"""Download page images from ABC Books IIIF collection.

Images are saved in one directory per book, which are named based on the book's ARK
identifier, with one JPEG per canvas named by the
canvas id. Images that have already been downloaded are skipped, so the
script can be re-run to resume an interrupted download.

Metadata is written to two CSV files in the output directory: books.csv (one row
per book/volume) and pages.csv (one row per canvas/page image). If the files
already exist, new rows are appended.

Usage:
  python scripts/download_images.py
  python scripts/download_images.py -o path/to/folder -c http://example.com/iiif/collection/manifest
"""

import argparse
import csv
import re
from pathlib import Path

import requests
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFException, IIIFPresentation
from tqdm import tqdm

TITLE_LENGTH = 40
ABC_COLLECTION = "https://figgy.princeton.edu/collections/deeb2da4-7db2-4514-b9b9-a6c76e164097/manifest"
DEFAULT_DATA_DIR = Path("local_data")

BOOK_FIELDS = ["book_id", "title", "manifest_url", "license"]
PAGE_FIELDS = ["book_id", "canvas_id", "label", "image_id"]

# extract the unique name from an ARK identifier in plain text or html-link, e.g.
# <a href='http://arks.princeton.edu/ark:/88435/1c18dk10w'>...</a>
re_ark_name = re.compile(r"ark:/\w+/(?P<name>[\w]+)")


def get_ark_name(manifest) -> str | None:
    """Get the name portion of the ARK identifier in manifest metadata."""
    for mdata in manifest.get("metadata", []):
        if mdata["label"].lower() == "identifier":
            match = re_ark_name.search(mdata["value"][0])
            if match:
                return match.group("name")
    return None


def get_title(manifest) -> str:
    """Get manifest label as a single string."""
    label = manifest.get("label", "")
    if isinstance(label, list):
        label = label[0] if label else ""
    if isinstance(label, dict):
        label = label.get("@value", "")
    return str(label)


def get_license(manifest) -> str:
    """Get license / rights statement from manifest (IIIF v2 or v3)."""
    value = manifest.get("license") or manifest.get("rights") or ""
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    return str(value)


def get_image_id(canvas) -> str:
    """Get the IIIF image identifier for a canvas."""
    image = IIIFImageClient.init_from_url(canvas["images"][0]["resource"]["@id"])
    return image.get_image_id()


def truncate(text: str, length: int = TITLE_LENGTH) -> str:
    """Truncate text to a fixed width for progress bar descriptions."""
    if len(text) > length:
        text = text[: length - 1] + "…"
    return text.ljust(length)


def download_collection_images(iiff_collection_url: str, output_dir: Path) -> None:
    collection = IIIFPresentation.from_url(iiff_collection_url)
    output_dir.mkdir(exist_ok=True)

    books_path = output_dir / "books.csv"
    pages_path = output_dir / "pages.csv"
    books_exists = books_path.is_file()
    pages_exists = pages_path.is_file()
    with (
        books_path.open("a", newline="") as books_file,
        pages_path.open("a", newline="") as pages_file,
    ):
        books_csv = csv.DictWriter(books_file, fieldnames=BOOK_FIELDS)
        pages_csv = csv.DictWriter(pages_file, fieldnames=PAGE_FIELDS)
        if not books_exists:
            books_csv.writeheader()
        if not pages_exists:
            pages_csv.writeheader()

        manifest_progress = tqdm(collection.manifests, desc="Manifests", position=0)
        for manifest in manifest_progress:
            manifest_progress.set_description(truncate(get_title(manifest)))
            download_images(manifest.id, output_dir, books_csv, pages_csv)


def download_images(
    url: str, output_dir: Path, books_csv: csv.DictWriter, pages_csv: csv.DictWriter
) -> None:
    try:
        manifest = IIIFPresentation.from_url(url)
    except IIIFException as err:
        tqdm.write(f"Error loading {url}: {err}")
        return

    # manifest seeAlso has catalog data for this collection
    identifier = get_ark_name(manifest)
    if not identifier:
        tqdm.write(f"No identifier found for {url}; skipping")
        return
    books_csv.writerow(
        {
            "book_id": identifier,
            "title": get_title(manifest),
            "manifest_url": url,
            "license": get_license(manifest),
        }
    )
    # output dir is assumed to be top-level directory; make an images directory,
    # with one subdirectory per book/volume, named by the ARK identifier
    book_image_dir = output_dir / "images" / identifier
    # make sure the image dir for this book/volume exists
    book_image_dir.mkdir(parents=True, exist_ok=True)

    # handle multivolume / multipart
    if hasattr(manifest, "manifests"):
        # similar to collection...
        for subvol in manifest.manifests:
            download_images(subvol.id, output_dir, books_csv, pages_csv)

    # multivol has no sequences
    if hasattr(manifest, "sequences"):
        canvases = manifest.sequences[0].canvases
        for canvas in tqdm(
            canvases, desc=f"  {identifier}", position=1, leave=False, unit="img"
        ):
            # save in folder by component id, with name based on canvas id
            canvas_id = canvas.short_id(canvas.id)
            image_filename = book_image_dir / f"{canvas_id}.jpg"
            pages_csv.writerow(
                {
                    "book_id": identifier,
                    "canvas_id": canvas_id,
                    "label": canvas.get("label", ""),
                    "image_id": get_image_id(canvas),
                }
            )
            # only download if we don't already have it
            if not image_filename.is_file():
                image_url = canvas["images"][0]["resource"]["@id"]
                image = requests.get(image_url)
                with image_filename.open("wb") as imgoutput:
                    imgoutput.write(image.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--collection", default=ABC_COLLECTION, help="IIIF collection manifest URL"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Directory for downloaded data (default: {DEFAULT_DATA_DIR})",
    )
    args = parser.parse_args()

    download_collection_images(args.collection, args.output_dir)


if __name__ == "__main__":
    main()
