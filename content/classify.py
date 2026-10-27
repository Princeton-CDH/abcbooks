import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def intro(mo):
    mo.md(r"""
    # Classifying ABC book pages from image embeddings

    Each page image in this dataset has been turned into an **embedding**: a list of 768 numbers
    produced by the [DINOv2](https://huggingface.co/facebook/dinov2-base) vision model. Images that
    look alike have embeddings that are close together.

    Some books also have **human-assigned tags** for each page (e.g. `hat`, `bird`, `tree`).
    In this notebook we will:

    1. load the embeddings and the tag metadata,
    2. join them so each image knows its tags,
    3. pick a tag and train a simple classifier that predicts whether a page has that tag,
    4. evaluate it and look at the pages it gets right and wrong.
    """)
    return


@app.cell
async def imports():
    import sys

    if sys.platform == "emscripten":
        # In the browser (WASM), install packages that aren't bundled with Pyodide
        import micropip

        # iconoscope v0.2.1 requires a newer polars than what is pre-installed with Pyodide;
        # install dependencies first and then install iconoscope without dependencies
        await micropip.install(
            ["h5py", "numpy", "pillow", "polars", "piffle", "pyarrow"]
        )
        await micropip.install("iconoscope", deps=False)

    from pathlib import Path

    import altair as alt
    import h5py
    import marimo as mo
    import numpy as np
    import polars as pl
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import GroupShuffleSplit
    from iconoscope.dataset import ImageDataset
    from piffle.image import IIIFImageClient

    return (
        GroupShuffleSplit,
        IIIFImageClient,
        ImageDataset,
        LogisticRegression,
        Path,
        alt,
        classification_report,
        confusion_matrix,
        mo,
        pl,
    )


@app.cell
async def paths(Path, mo):
    # Data files live in `data/` next to this notebook. When running in the
    # browser (WASM), they're served by the website, so we download them first.
    data_dir = mo.notebook_location() / "data"

    async def data_file(name):
        """Return a local path for a data file, downloading it if needed."""
        if isinstance(data_dir, Path):
            return data_dir / name
        from pyodide.http import pyfetch

        _resp = await pyfetch(str(data_dir / name))
        Path(name).write_bytes(await _resp.bytes())
        return Path(name)

    embeddings_file = await data_file("abc_books_subset.h5")
    pages_file = await data_file("pages.parquet")
    tags_file = await data_file("tags.parquet")
    image_metadata_file = await data_file("image_metadata.parquet")
    return embeddings_file, image_metadata_file, pages_file, tags_file


@app.cell
def load_md(mo):
    mo.md(r"""
    ## Load the data

    We have pre-computed image embeddings and data about books and page-level tags from ABC Books.

    Image embeddings and metadata are connected by the IIIF **canvas id**

    Tags are lower-cased and de-duplicated. Images without any tags are dropped.
    """)
    return


@app.cell
def load_h5(ImageDataset, embeddings_file, mo, pl):
    img_dataset = ImageDataset(embeddings_file)

    from iconoscope.models import EmbeddingConfig, EmbeddingModel, DEFAULT_MODEL

    default_config = EmbeddingConfig(model=DEFAULT_MODEL)

    embeddings_df = img_dataset.load_data(
        features=True, config=default_config
    )  # includes image paths by default

    embeddings_df = embeddings_df.with_columns(
        # extract canvas id from filenames used to create the dataset
        canvas_id=pl.col.image_path.str.split("/")
        .list.last()
        .str.replace(r"\.jpg$", ""),
    )

    mo.md(f"Loaded features for **{embeddings_df.shape[0]:,} images**")
    return (embeddings_df,)


@app.cell
def load_meta(IIIFImageClient, image_metadata_file, pages_file, pl, tags_file):
    pages_df = pl.read_parquet(pages_file).with_columns(
        canvas_id=pl.col.CANVAS.str.split("/").list.last()
    )
    tags_df = (
        pl.read_parquet(tags_file)
        .with_columns(tag=pl.col.tag.str.strip_chars().str.to_lowercase())
        .unique()
    )
    images_df = pl.read_parquet(image_metadata_file).select(
        canvas_id="id",
        thumbnail=pl.col.image_iiif_id.map_elements(
            lambda url: str(IIIFImageClient.init_from_url(url).size(width=500)),
            return_dtype=pl.String,
        ),
    )
    return images_df, pages_df, tags_df


@app.cell
def join(embeddings_df, images_df, mo, pages_df, pl, tags_df):
    # one row per image: embedding row, book, page, and its list of tags
    page_tags_df = (
        embeddings_df.join(pages_df, on="canvas_id", how="inner")
        .join(
            tags_df.group_by("post_id").agg(tags=pl.col.tag),
            left_on="PAGE_ID",
            right_on="post_id",
            how="inner",
        )
        .join(images_df, on="canvas_id", how="left")
        .sort("canvas_id")
    )
    mo.vstack(
        [
            mo.md(
                f"**{page_tags_df.height}** of {embeddings_df.height} images have tags, from **{page_tags_df['BOOK_ID'].n_unique()}** books."
            ),
            page_tags_df.select("TITLE", "BOOK_ID", "PAGENUM", "tags"),
        ]
    )
    return (page_tags_df,)


@app.cell
def tag_counts(mo, page_tags_df, pl):
    tag_counts = (
        page_tags_df.explode("tags")
        .group_by(tag="tags")
        .agg(pages=pl.len(), books=pl.col.BOOK_ID.n_unique())
        .sort("pages", descending=True)
    )
    mo.vstack(
        [
            mo.md(
                "### Most common tags\nA tag needs enough examples (in several books) to learn from."
            ),
            tag_counts.head(30),
        ]
    )
    return (tag_counts,)


@app.cell
def pick_md(mo):
    mo.md(r"""
    ## Train a classifier

    Choose a tag. Every page is labeled **1** if it has the tag and **0** otherwise, and we
    fit a **logistic regression** on the embeddings.

    We split train/test **by book**, not by page: pages from the same book share a style,
    so testing on a book the model has seen would make it look better than it really is.
    """)
    return


@app.cell
def controls(mo, pl, tag_counts):
    _options = tag_counts.filter(pl.col.pages >= 30, pl.col.books >= 4)["tag"].to_list()
    tag_select = mo.ui.dropdown(
        options=_options,
        value="bird" if "bird" in _options else _options[0],
        label="Tag",
        searchable=True,
    )
    test_size = mo.ui.slider(
        0.1,
        0.5,
        step=0.05,
        value=0.25,
        label="Fraction of books held out for testing",
        show_value=True,
    )
    balanced = mo.ui.checkbox(
        value=True,
        label="Balance classes (tags are rare, so weight positive examples more)",
    )
    mo.vstack([tag_select, test_size, balanced])
    return balanced, tag_select, test_size


@app.cell
def train(
    GroupShuffleSplit,
    LogisticRegression,
    balanced,
    mo,
    page_tags_df,
    tag_select,
    test_size,
):
    target_tag = tag_select.value
    y = page_tags_df["tags"].list.contains(target_tag).to_numpy().astype(int)
    X = page_tags_df["features"].to_numpy()
    groups = page_tags_df["BOOK_ID"].to_numpy()

    _split = GroupShuffleSplit(n_splits=1, test_size=test_size.value, random_state=0)
    train_idx, test_idx = next(_split.split(X, y, groups))

    model = LogisticRegression(
        max_iter=2000, class_weight="balanced" if balanced.value else None
    )
    model.fit(X[train_idx], y[train_idx])
    probs = model.predict_proba(X[test_idx])[:, 1]
    preds = (probs >= 0.5).astype(int)

    mo.md(
        f"Training on **{len(train_idx)}** pages ({y[train_idx].sum()} with `{target_tag}`), "
        f"testing on **{len(test_idx)}** pages from unseen books ({y[test_idx].sum()} with `{target_tag}`)."
    )
    return preds, probs, target_tag, test_idx, y


@app.cell
def eval_md(mo):
    mo.md(r"""
    ## Evaluate

    * **Precision**: of the pages the model flagged, how many really have the tag?
    * **Recall**: of the pages that really have the tag, how many did the model find?
    * Compare **accuracy** to the baseline of always guessing "no tag" — for rare tags it can be high without learning anything.
    """)
    return


@app.cell
def evaluate(
    alt,
    classification_report,
    confusion_matrix,
    mo,
    pl,
    preds,
    target_tag,
    test_idx,
    y,
):
    _cm = confusion_matrix(y[test_idx], preds, labels=[0, 1])
    _cm_df = pl.DataFrame(
        {
            "actual": ["no " + target_tag, target_tag] * 2,
            "predicted": ["no " + target_tag] * 2 + [target_tag] * 2,
            "pages": [_cm[0, 0], _cm[1, 0], _cm[0, 1], _cm[1, 1]],
        }
    )
    _chart = (
        alt.Chart(_cm_df)
        .mark_rect()
        .encode(
            x="predicted:N",
            y="actual:N",
            color=alt.Color("pages:Q", scale=alt.Scale(scheme="blues")),
        )
        + alt.Chart(_cm_df)
        .mark_text(fontSize=16)
        .encode(x="predicted:N", y="actual:N", text="pages:Q")
    ).properties(width=250, height=250, title="Confusion matrix")
    _baseline = 1 - y[test_idx].mean()
    mo.hstack(
        [
            _chart,
            mo.vstack(
                [
                    mo.md(f"Baseline (always 'no'): **{_baseline:.1%}**"),
                    mo.plain_text(
                        classification_report(
                            y[test_idx],
                            preds,
                            labels=[0, 1],
                            target_names=["no " + target_tag, target_tag],
                            zero_division=0,
                        )
                    ),
                ]
            ),
        ]
    )
    return


@app.cell
def examples_md(mo):
    mo.md(r"""
    ## Review the results

    Numbers only tell part of the story. Which pages does the model think are most likely
    to have the tag? Are the "mistakes" really mistakes, or missing tags?
    """)
    return


@app.cell
def thumb_size_control(mo):
    thumb_size = mo.ui.slider(
        100, 500, step=25, value=200, label="Thumbnail size (px)", show_value=True
    )
    thumb_size
    return (thumb_size,)


@app.cell
def examples(
    mo,
    page_tags_df,
    pl,
    preds,
    probs,
    target_tag,
    test_idx,
    thumb_size,
    y,
):
    results_df = page_tags_df[test_idx].with_columns(
        probability=pl.Series(probs),
        actual=pl.Series(y[test_idx]),
        predicted=pl.Series(preds),
    )

    def _gallery(df, title):
        _items = [
            mo.vstack(
                [
                    mo.image(r["thumbnail"], width=thumb_size.value),
                    mo.md(f"<small>{r['TITLE']}<br>p={r['probability']:.2f}</small>"),
                ]
            ).style(width=f"{thumb_size.value}px", flex="none")
            for r in df.iter_rows(named=True)
        ]
        return mo.vstack(
            [mo.md(f"### {title}"), mo.hstack(_items, wrap=True, justify="start")]
        )

    mo.ui.tabs(
        {
            "Most confident": _gallery(
                results_df.sort("probability", descending=True).head(12),
                f"Highest predicted probability of '{target_tag}'",
            ),
            "False positives": _gallery(
                results_df.filter((pl.col.predicted == 1) & (pl.col.actual == 0))
                .sort("probability", descending=True)
                .head(12),
                "Predicted but not tagged",
            ),
            "False negatives": _gallery(
                results_df.filter((pl.col.predicted == 0) & (pl.col.actual == 1))
                .sort("probability")
                .head(12),
                "Tagged but missed",
            ),
        }
    )
    return


@app.cell
def exercises(mo):
    mo.md(r"""
    ## Try it yourself

    1. Try several tags. Which are easy to learn (`flag`? `bird`?) and which are hard (`rhyme`?)? Why might a *visual* model struggle with some tags?
    2. Turn off class balancing. What happens to precision and recall for a rare tag?
    3. Change the decision threshold from 0.5 — how does that trade precision against recall?
    4. Replace `LogisticRegression` with `sklearn.neighbors.KNeighborsClassifier`. Does it do better?
    5. Look at the false positives: are some of them pages that *should* have been tagged?
    """)
    return


if __name__ == "__main__":
    app.run()
