#!/usr/bin/env python
"""Download page images from a IIIF collection or manifest (default: ABC Books).

Images are saved in one directory per book, which are named based on the book's ARK
identifier, with one JPEG per canvas named by the
canvas id. Images that have already been downloaded are skipped, so the
script can be re-run to resume an interrupted download.

Metadata is written to two CSV files in the output directory: books.csv (one row
per book/volume) and pages.csv (one row per canvas/page image). Rows for a book
are written only once all of its pages are downloaded. If the files already
exist, new rows are appended; books listed in books.csv with a page count
matching their rows in pages.csv are considered complete and skipped.

Manifests that require authorization (e.g. restricted or reading-room-only
content) are intentionally skipped and counted, not treated as errors: we only
want to use openly accessible content.

Press Ctrl-C once to stop after the current book; press again to quit immediately.

Usage:
  python scripts/download_images.py
  python scripts/download_images.py http://example.com/iiif/book/manifest
  python scripts/download_images.py -o path/to/folder http://example.com/iiif/collection/manifest
"""

import argparse
import csv
import re
import signal
from collections import Counter
from pathlib import Path

import requests
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFException, IIIFPresentation
from tqdm import tqdm

TITLE_LENGTH = 40
ABC_COLLECTION = "https://figgy.princeton.edu/collections/deeb2da4-7db2-4514-b9b9-a6c76e164097/manifest"
DEFAULT_DATA_DIR = Path("local_data")

BOOK_FIELDS = ["book_id", "title", "manifest_url", "license", "page_count"]
PAGE_FIELDS = ["book_id", "canvas_id", "label", "image_id"]

# extract the unique name from an ARK identifier in plain text or html-link, e.g.
# <a href='http://arks.princeton.edu/ark:/88435/1c18dk10w'>...</a>
re_ark_name = re.compile(r"ark:/\w+/(?P<name>[\w]+)")


# set by the first Ctrl-C; checked after each book
stop_requested = False

# running totals, shown on the progress bar and summarized at the end
stats = Counter()


def request_stop(signum, frame) -> None:
    """On first Ctrl-C, finish the current book then stop; restore the
    default handler so a second Ctrl-C quits immediately."""
    global stop_requested
    stop_requested = True
    signal.signal(signal.SIGINT, signal.default_int_handler)
    tqdm.write("Stopping after current book; press Ctrl-C again to quit now")


def load_completed(books_path: Path, pages_path: Path) -> dict[str, int]:
    """Get ids and page counts of books with all pages recorded in previous runs."""
    if not books_path.is_file() or not pages_path.is_file():
        return {}
    with pages_path.open(newline="") as pages_file:
        page_counts = Counter(row["book_id"] for row in csv.DictReader(pages_file))
    with books_path.open(newline="") as books_file:
        return {
            row["book_id"]: int(row["page_count"])
            for row in csv.DictReader(books_file)
            if page_counts[row["book_id"]] == int(row["page_count"])
        }


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


def download(
    url: str,
    output_dir: Path,
    books_csv: csv.DictWriter,
    pages_csv: csv.DictWriter,
    completed: dict[str, int],
    depth: int = 0,
) -> None:
    """Download images and metadata for a IIIF collection, multi-volume work,
    or single book manifest. Collections and multi-volume works are handled
    recursively; ``depth`` is used to position stacked progress bars."""
    try:
        manifest = IIIFPresentation.from_url(url)
    except IIIFException as err:
        # restricted manifests return 401/403, or redirect to a login page;
        # skip them intentionally, since we only use openly accessible content
        if any(msg in str(err) for msg in ("401", "403", "No JSON found")):
            stats["unauthorized manifests"] += 1
        else:
            stats["errored manifests"] += 1
            tqdm.write(f"Error loading {url}: {err}")
        return

    # books and volumes are identified by ARK; collections don't have one
    identifier = get_ark_name(manifest)
    if identifier in completed:
        stats["books already complete"] += 1
        stats["pages already complete"] += completed[identifier]
        return

    # collection or multi-volume work: download each member manifest
    if hasattr(manifest, "manifests"):
        members = tqdm(
            manifest.manifests,
            desc=truncate(get_title(manifest)),
            position=depth,
            leave=depth == 0,
            unit="book",
        )
        for member in members:
            download(member.id, output_dir, books_csv, pages_csv, completed, depth + 1)
            members.set_postfix(unauthorized=stats["unauthorized manifests"])
            # stop before recording a partially downloaded multi-volume work
            if stop_requested:
                return

    if not identifier:
        if not hasattr(manifest, "manifests"):
            stats["errored manifests"] += 1
            tqdm.write(f"No identifier found for {url}; skipping")
        return

    # one image directory per book/volume, named by the ARK identifier
    book_image_dir = output_dir / "images" / identifier
    book_image_dir.mkdir(parents=True, exist_ok=True)

    # collect page rows and write them with the book row once all pages are done,
    # so an interrupted book is not recorded as complete
    pages = []
    # multivol has no sequences
    if hasattr(manifest, "sequences"):
        canvases = manifest.sequences[0].canvases
        for canvas in tqdm(
            canvases,
            desc=truncate(get_title(manifest)),
            position=depth,
            leave=False,
            unit="img",
        ):
            # save in folder by component id, with name based on canvas id
            canvas_id = canvas.short_id(canvas.id)
            image_filename = book_image_dir / f"{canvas_id}.jpg"
            pages.append(
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
                stats["pages downloaded"] += 1

    pages_csv.writerows(pages)
    books_csv.writerow(
        {
            "book_id": identifier,
            "title": get_title(manifest),
            "manifest_url": url,
            "license": get_license(manifest),
            "page_count": len(pages),
        }
    )
    stats["books downloaded"] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "url",
        nargs="?",
        default=ABC_COLLECTION,
        help="IIIF collection or manifest URL (default: ABC Books collection)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Directory for downloaded data (default: {DEFAULT_DATA_DIR})",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    books_path = output_dir / "books.csv"
    pages_path = output_dir / "pages.csv"
    completed = load_completed(books_path, pages_path)
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

        signal.signal(signal.SIGINT, request_stop)
        download(args.url, output_dir, books_csv, pages_csv, completed)

    print("\nSummary:")
    for label in [
        "books downloaded",
        "pages downloaded",
        "books already complete",
        "pages already complete",
        "unauthorized manifests",
        "errored manifests",
    ]:
        print(f"  {label:<24} {stats[label]:>6}")


if __name__ == "__main__":
    main()
