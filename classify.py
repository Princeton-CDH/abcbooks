import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
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


    /// admonition | About this notebook

    This is a [marimo](https://marimo.io) notebook that has been exported to HTML+WASM so it can run in the browser.

    This notebook is running in **edit** mode with the code blocks hidden by default. If you are interested in seeing how it is implemented, click into a collapsed block to view the code.

    Switch to **application view** using the ::lucide:layout-template:: button in the bottom right menu. Use the ::lucide:square-pen:: to switch back to **edit view**.

    ///
    """)


@app.cell(hide_code=True)
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
    import marimo as mo
    import polars as pl
    from iconoscope.dataset import ImageDataset
    from piffle.image import IIIFImageClient
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import GroupShuffleSplit

    return (
        GroupShuffleSplit,
        IIIFImageClient,
        ImageDataset,
        Path,
        RandomForestClassifier,
        alt,
        classification_report,
        confusion_matrix,
        mo,
        pl,
    )


@app.cell(hide_code=True)
async def paths(Path, mo):
    # Data files live in `public/data/` next to this notebook. When running in the
    # browser (WASM), they're served by the website, so we download them first.
    data_dir = mo.notebook_location() / "public" / "data"

    async def data_file(name):
        """Return a local path for a data file, downloading it if needed."""
        if isinstance(data_dir, Path):
            return data_dir / name
        from pyodide.http import pyfetch

        _resp = await pyfetch(str(data_dir / name))
        Path(name).write_bytes(await _resp.bytes())
        return Path(name)

    embeddings_file = await data_file("abcbooks.h5")
    pages_file = await data_file("pages.csv")
    tags_file = await data_file("page_tags.csv")
    books_file = await data_file("books.csv")
    return books_file, embeddings_file, pages_file, tags_file


@app.cell(hide_code=True)
def load_md(mo):
    mo.md(r"""
    ## Load the data

    We have pre-computed image embeddings and data about books and page-level tags from ABC Books.

    Image embeddings and metadata are connected by the IIIF **canvas id**

    Tags are lower-cased and de-duplicated. Not every page has been tagged: we train and
    evaluate on tagged pages, then use the model to suggest tags for untagged pages.
    """)


@app.cell(hide_code=True)
def load_h5(ImageDataset, embeddings_file, mo, pl):
    img_dataset = ImageDataset(embeddings_file)

    from iconoscope.models import DEFAULT_MODEL, EmbeddingConfig

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


@app.cell(hide_code=True)
def load_meta(IIIFImageClient, books_file, pages_file, pl, tags_file):
    # IIIF image API endpoint for Princeton (Figgy) images
    iiif_image_api = "https://iiif-cloud.princeton.edu/iiif/2"
    # includes canvas_id, page label, and IIIF image_id from prep_data.py;
    # add book title from books file
    pages_df = (
        pl.read_csv(pages_file, schema_overrides={"label": pl.String}).join(
            pl.read_csv(books_file).select(
                "book_id",
                # drop subtitle (after colon) from long titles
                title=pl.when(
                    (pl.col.title.str.len_chars() > 50) & pl.col.title.str.contains(":")
                )
                .then(pl.col.title.str.split(":").list.first().str.strip_chars())
                .otherwise(pl.col.title),
            ),
            on="book_id",
            how="left",
        )
    ).with_columns(
        thumbnail=pl.col.image_id.map_elements(
            lambda img_id: str(IIIFImageClient(iiif_image_api, img_id).size(width=500)),
            return_dtype=pl.String,
        ),
    )
    tags_df = pl.read_csv(tags_file)  # already normalized in prep_data.py
    return pages_df, tags_df


@app.cell(hide_code=True)
def join(embeddings_df, mo, pages_df, pl, tags_df):
    # one row per image: embedding row, book, page, and its list of tags
    # (null tags = page has not been tagged)
    all_pages_df = (
        embeddings_df.join(pages_df, on="canvas_id", how="inner")
        .join(
            tags_df.group_by("page_id").agg(tags=pl.col.tag),
            on="page_id",
            how="left",
        )
        .with_columns(is_tagged=pl.col.tags.is_not_null())
        .sort("canvas_id")
    )
    # tagged pages have known labels: use them for training and evaluation
    page_tags_df = all_pages_df.filter(pl.col.is_tagged)
    untagged_df = all_pages_df.filter(~pl.col.is_tagged)
    mo.vstack(
        [
            mo.md(
                f"**{all_pages_df.height:,}** of {embeddings_df.height:,} images have page metadata, "
                f"from **{all_pages_df['book_id'].n_unique()}** books: "
                f"**{page_tags_df.height:,}** tagged, **{untagged_df.height:,}** untagged."
            ),
            all_pages_df.with_columns(tags=pl.col.tags.list.join(", ")).select(
                "thumbnail",
                "title",
                "label",
                "tags",
            ),
        ]
    )
    return page_tags_df, untagged_df


@app.cell(hide_code=True)
def tag_counts(mo, page_tags_df, pl):
    tag_counts = (
        page_tags_df.explode("tags")
        .group_by(tag="tags")
        .agg(pages=pl.len(), books=pl.col.book_id.n_unique())
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


@app.cell(hide_code=True)
def pick_md(mo):
    mo.md(r"""
    ## Train a classifier

    Choose a tag and click **Train**. Every tagged page is labeled **1** if it has the tag and **0** otherwise, and we
    fit a **random forest** (an ensemble of decision trees) on the embeddings.

    We split train/test **by book**, not by page: pages from the same book share a style,
    so testing on a book the model has seen would make it look better than it really is.
    """)


@app.cell(hide_code=True)
def controls(mo, pl, tag_counts):
    _options = tag_counts.filter(pl.col.pages >= 30, pl.col.books >= 4)["tag"].to_list()
    tag_select = mo.ui.dropdown(
        options=_options,
        value=None,
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
    train_button = mo.ui.run_button(label="Train classifier", kind="success")
    mo.vstack([tag_select, test_size, balanced, train_button])
    return balanced, tag_select, test_size, train_button


@app.cell(hide_code=True)
def train(
    GroupShuffleSplit,
    RandomForestClassifier,
    balanced,
    mo,
    page_tags_df,
    tag_select,
    test_size,
    train_button,
):
    mo.stop(
        tag_select.value is None or not train_button.value,
        mo.md("_Choose a tag and click **Train classifier** to fit a model._"),
    )
    target_tag = tag_select.value
    y = page_tags_df["tags"].list.contains(target_tag).to_numpy().astype(int)
    X = page_tags_df["features"].to_numpy()
    groups = page_tags_df["book_id"].to_numpy()

    _split = GroupShuffleSplit(n_splits=1, test_size=test_size.value, random_state=0)
    train_idx, test_idx = next(_split.split(X, y, groups))

    model = RandomForestClassifier(
        n_estimators=500,
        min_samples_leaf=2,
        class_weight="balanced" if balanced.value else None,
        random_state=0,
    )
    with mo.status.spinner(title=f"Training a random forest for '{target_tag}'..."):
        model.fit(X[train_idx], y[train_idx])
    probs = model.predict_proba(X[test_idx])[:, 1]
    preds = (probs >= 0.5).astype(int)

    mo.md(
        f"Training on **{len(train_idx)}** pages ({y[train_idx].sum()} with `{target_tag}`), "
        f"testing on **{len(test_idx)}** pages from unseen books ({y[test_idx].sum()} with `{target_tag}`)."
    )
    return model, preds, probs, target_tag, test_idx, y


@app.cell(hide_code=True)
def eval_md(mo):
    mo.md(r"""
    ## Evaluate

    * **Precision**: of the pages the model flagged, how many really have the tag?
    * **Recall**: of the pages that really have the tag, how many did the model find?
    * Compare **accuracy** to the baseline of always guessing "no tag" — for rare tags it can be high without learning anything.
    """)


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
def examples_md(mo):
    mo.md(r"""
    ## Review the results

    Numbers only tell part of the story. Which pages does the model think are most likely
    to have the tag? Are the "mistakes" really mistakes, or missing tags?
    """)


@app.cell(hide_code=True)
def thumb_size_control(mo):
    thumb_size = mo.ui.slider(
        100, 500, step=25, value=200, label="Thumbnail size (px)", show_value=True
    )
    thumb_size
    return (thumb_size,)


@app.cell(hide_code=True)
def gallery_fn(mo, thumb_size):
    _gallery_css = """
    <style>
    .abc-gallery { display:flex; flex-wrap:wrap; gap:12px; position:relative; }
    .abc-item { flex:none; position:relative; }
    .abc-thumb { display:block; width:100%; border-radius:4px; cursor:zoom-in; }
    .abc-pop { display:none; position:absolute; top:0; left:100%; margin-left:8px; z-index:1000;
      width:500px; max-width:60vw; background:var(--background, white); padding:4px;
      border:1px solid #ccc; border-radius:6px; box-shadow:0 4px 16px rgba(0,0,0,.3); pointer-events:none; }
    .abc-pop img { width:100%; display:block; }
    .abc-item:hover .abc-pop { display:block; }
    .abc-item.abc-right .abc-pop { left:auto; right:100%; margin-left:0; margin-right:8px; }
    .abc-bar { height:6px; background:#e5e7eb; border-radius:3px; overflow:hidden; margin-top:4px; }
    .abc-bar > div { height:100%; }
    .abc-caption { font-size:0.8em; line-height:1.3; margin-top:2px; }
    </style>
    """

    def _prob_color(p):
        """Red (weak) -> amber -> green (strong)."""
        if p >= 0.75:
            return "#16a34a"
        if p >= 0.5:
            return "#84cc16"
        if p >= 0.25:
            return "#f59e0b"
        return "#ef4444"

    def gallery(df, title):
        """Thumbnails with title and predicted probability for each page.

        Hover a thumbnail to see a larger version; the bar shows prediction strength.
        """
        _w = thumb_size.value
        _items = []
        for _i, r in enumerate(df.iter_rows(named=True)):
            _p = r["probability"]
            _side = " abc-right" if _i % 4 >= 2 else ""
            _items.append(
                f'<div class="abc-item{_side}" style="width:{_w}px">'
                f'<img class="abc-thumb" src="{r["thumbnail"]}" loading="lazy">'
                f'<div class="abc-pop"><img src="{r["thumbnail"]}"></div>'
                f'<div class="abc-bar" title="p={_p:.2f}"><div style="width:{_p * 100:.0f}%;background:{_prob_color(_p)}"></div></div>'
                f'<div class="abc-caption">{r["title"]}<br>{r["label"] or ""}<br><b>p={_p:.2f}</b></div>'
                "</div>"
            )
        _body = "".join(_items) if _items else "<em>No pages to show.</em>"
        return mo.vstack(
            [
                mo.md(f"### {title}"),
                mo.Html(_gallery_css + f'<div class="abc-gallery">{_body}</div>'),
            ]
        )

    return (gallery,)


@app.cell(hide_code=True)
def examples(
    gallery,
    mo,
    page_tags_df,
    pl,
    preds,
    probs,
    target_tag,
    test_idx,
    y,
):
    results_df = page_tags_df[test_idx].with_columns(
        probability=pl.Series(probs),
        actual=pl.Series(y[test_idx]),
        predicted=pl.Series(preds),
    )

    mo.ui.tabs(
        {
            "Most confident": gallery(
                results_df.sort("probability", descending=True).head(12),
                f"Highest predicted probability of '{target_tag}'",
            ),
            "False positives": gallery(
                results_df.filter((pl.col.predicted == 1) & (pl.col.actual == 0))
                .sort("probability", descending=True)
                .head(12),
                "Predicted but not tagged",
            ),
            "False negatives": gallery(
                results_df.filter((pl.col.predicted == 0) & (pl.col.actual == 1))
                .sort("probability")
                .head(12),
                "Tagged but missed",
            ),
        }
    )


@app.cell(hide_code=True)
def predict_md(mo):
    mo.md(r"""
    ## Suggest tags for untagged pages

    Pages that were never tagged have no labels, so we left them out of training and
    evaluation. Now we can use the model to suggest which of them might have the tag.
    """)


@app.cell(hide_code=True)
def predict_untagged(gallery, mo, model, pl, target_tag, untagged_df):
    if untagged_df.is_empty():
        _out = mo.md("All pages with metadata are tagged; nothing to predict.")
    else:
        untagged_preds_df = untagged_df.with_columns(
            probability=pl.Series(
                model.predict_proba(untagged_df["features"].to_numpy())[:, 1]
            )
        ).sort("probability", descending=True)
        _n_flagged = (untagged_preds_df["probability"] >= 0.5).sum()
        # skip pages the model is essentially certain do NOT have the tag (p rounds to 0.00)
        _candidates = untagged_preds_df.filter(pl.col.probability >= 0.005)
        _out = mo.vstack(
            [
                mo.md(
                    f"The model suggests `{target_tag}` for **{_n_flagged:,}** of "
                    f"{untagged_df.height:,} untagged pages (p ≥ 0.5). "
                    f"{_candidates.height:,} pages have a non-zero probability. "
                    "The colored bar shows prediction strength; hover a page to enlarge it."
                ),
                gallery(
                    _candidates.head(12),
                    f"Untagged pages most likely to show '{target_tag}'",
                ),
            ]
        )
    _out


@app.cell(hide_code=True)
def exercises(mo):
    mo.md(r"""
    ## Try it yourself

    1. Try several tags. Which are easy to learn (`flag`? `bird`?) and which are hard (`rhyme`?)? Why might a *visual* model struggle with some tags?
    2. Turn off class balancing. What happens to precision and recall for a rare tag?
    3. Change the decision threshold from 0.5 — how does that trade precision against recall?
    4. Replace `RandomForestClassifier` with `sklearn.linear_model.LogisticRegression` or `sklearn.neighbors.KNeighborsClassifier`. Is it faster? Does it do better?
    5. Look at the false positives: are some of them pages that *should* have been tagged?
    """)


@app.cell(hide_code=True)
def _(books_file, mo, pl):
    # display table of books included in this dataset
    def dpul_link(pul_id: str) -> str:
        return mo.Html(
            f"<a href='https://dpul.princeton.edu/cotsen/catalog/{pul_id}' target='_blank'>View on DPUL</a>"
        )

    # when running on locally, use a relative path
    img_base_path = "/public/assets/rights/"
    # when running on web assembly, use the base url for the notebook
    notebook_location = str(mo.notebook_location())
    if notebook_location.startswith("http"):
        img_base_path = f"{notebook_location}{img_base_path}"

    def license(uri: str) -> str:
        img = None

        match uri:
            case "https://creativecommons.org/publicdomain/mark/1.0/":
                img = "cc-publicdomain.svg"
            case "http://rightsstatements.org/vocab/NKC/1.0/":
                img = "rs-other-unknown.svg"
            case "http://rightsstatements.org/vocab/CNE/1.0/":
                img = "rs-other-notevaluated.svg"

        if img is not None:
            link_text = f'<img src="{img_base_path}{img}"/>'
        else:
            link_text = uri

        return mo.Html(f"<a href='{uri}' target='_blank'>{link_text}</a>")

    # NOTE: abcbooks class site now uses slugs instead of numeric ids, so current data doesn't support linking
    # directly to books on the class site.
    # If this functionality is desired, we'll need to request an updated version of the data with slugs

    books_df = pl.read_csv(books_file).with_columns(
        # add links to dpul, abc books, image for license
        dpul_link=pl.col.book_id.map_elements(dpul_link),
        license_uri=pl.col.license,
        license=pl.col.license.map_elements(license),
    )

    # display list of books in a nicely formatted table
    book_table = mo.ui.table(
        books_df.select(
            "title",
            "page_count",
            "license",
            "dpul_link",
        ).rename(
            {
                "title": "Title",
                "license": "Rights",
                "dpul_link": "Link",
                "page_count": "Pages",
            }
        ),
        selection=None,  # disable select box
        pagination=False,  # show all rows
        # label="Books",
        show_download=False,
        show_data_types=False,
        column_widths={"Title": 500},
    )

    mo.accordion(
        {
            "Books": mo.vstack(
                [
                    mo.md(
                        "This is the full list of the books that have pages included in this notebook, along with the rights status. Use the view link to look at books on Princeton University Library's Digital PUL."
                    ),
                    book_table,
                ]
            )
        }
    )


@app.cell(hide_code=True)
def _():
    # uncomment to report the the distinct set of license URIs in the data
    # books_df["license_uri"].unique()
    return


if __name__ == "__main__":
    app.run()
