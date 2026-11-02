#!/usr/bin/env python
"""Download page images from ABC Books IIIF collection.

Images are saved in one directory per book, which are named based on the book's ARK
identifier, with one JPEG per canvas named by the
canvas id. Images that have already been downloaded are skipped, so the
script can be re-run to resume an interrupted download.

Usage:
  python scripts/download_images.py
  python scripts/download_images.py -o path/to/folder -c http://example.com/iiif/collection/manifest
"""

import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from piffle.presentation import IIIFException, IIIFPresentation

ABC_COLLECTION = "https://figgy.princeton.edu/collections/deeb2da4-7db2-4514-b9b9-a6c76e164097/manifest"
DEFAULT_OUTPUT_DIR = Path("abcbook-images")


def download_collection_images(iiff_collection_url: str, output_dir: Path) -> None:
    collection = IIIFPresentation.from_url(iiff_collection_url)
    output_dir.mkdir(exist_ok=True)

    for manifest in collection.manifests:
        print(f"Downloading manifest {manifest.label[0]} {manifest.id}")
        download_images(manifest.id, output_dir)


def download_images(url: str, output_dir: Path) -> None:
    try:
        manifest = IIIFPresentation.from_url(url)
    except IIIFException as err:
        print(err)
        return

    # manifest seeAlso has catalog data for this collection
    identifier = None
    for mdata in manifest.metadata:
        if mdata["label"].lower() == "identifier":
            identifier = mdata["value"][0]
            break

    # ark identifier is either bare string or html link, so parse out the ark url if needed
    if identifier and identifier.startswith("<a href"):
        id_tag = BeautifulSoup(identifier, "html.parser")
        identifier = next(iter(id_tag.strings))  # full ark url
        identifier = identifier[
            identifier.find("ark:/") :
        ]  # get substring starting with ark:/
        # identifier=='http://arks.princeton.edu/ark:/88435/1c18dk10w' alt='Identifier'>http://arks.princeton.edu/ark:/88435/1c18dk10w</a>"")

    # convert ark identifier for filename safe
    file_id = identifier.replace("/", "-").replace(":", "-")

    book_image_dir = output_dir / file_id
    # make sure the image dir for this book/volume exists
    if not book_image_dir.is_dir():
        book_image_dir.mkdir()

    # handle multivolume / multipart
    if hasattr(manifest, "manifests"):
        # similar to collection...
        for subvol in manifest.manifests:
            download_images(subvol.id, output_dir)

    # multivol has no sequences
    if hasattr(manifest, "sequences"):
        for canvas in manifest.sequences[0].canvases:
            # save in folder by component id, with name based on canvas id
            canvas_id = canvas.short_id(canvas.id)
            image_filename = book_image_dir / f"{canvas_id}.jpg"
            # only download if we don't already have it
            if not image_filename.is_file():
                image_url = canvas["images"][0]["resource"]["@id"]
                print(f"downloading {image_url}")
                image = requests.get(image_url)
                with image_filename.open("wb") as imgoutput:
                    imgoutput.write(image.content)

                print(f"saved image as {image_filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--collection", default=ABC_COLLECTION, help="IIIF collection manifest URL"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for downloaded data (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    download_collection_images(args.collection, args.output_dir)


if __name__ == "__main__":
    main()
