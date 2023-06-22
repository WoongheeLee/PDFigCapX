# PdfFigCapx

Python3 implementation of Li et al. [_Figure and caption extraction from biomedical documents_](https://academic.oup.com/bioinformatics/article/35/21/4381/5428177) (2018).
PdfFigCapx extracts figures and captions from PDF documents, and returns the
extracted content and associated metadata.

## 1. Installation

### 1.1 Pre-requisites

The project relies on [ChromeDriver](https://chromedriver.chromium.org/downloads)
and pdf2html utility from [Xpdf command line tools](https://www.xpdfreader.com/download.html).
The library will look by default for ChromDriver at _/usr/bin_ but you can provide
a custom path. For pdf2html, make sure the binaries are added to your PATH or
in _/usr/bin_.

### 1.2 Install the Poetry project

You can install the Poetry project and execute the commands using the poetry
environment.

```bash
// clone the repository
cd pdfigcapx
poetry install
```

## 2. Usage

## 2.1 Process every PDF inside a folder

Process every PDF and create a folder per PDF with the images and captions inside `OUTPUT_FOLDER`:

```bash
cd pdfigcapx
poetry run python src/batch_processing.py INPUT_FOLDER ARTIFACTS_FOLDER OUTPUT_FOLDER --logs_path LOGS_FOLDER --num_workers 10
```

Optional parameters:

- --no-individual-folders: add to avoid creating one folder per PDF and instead
  add all the outputs to the `OUTPUT_FOLDER`
- --reprocess-errors: add to reprocess any PDF that generated a processing error
  on a previous run
- --logs_path: If not specified, uses the `OUTPUT_FOLDER`

## 2.2 Outputs

For every PDF the script generates:

- `PDF_NAME`.json: output metadata
- One JPG image per image found with the naming convention `PDF_NAME`\_PAGE-NUMBER_IMG-NUMBER.jpg, being the IMG-NUMBER a consecutive number
  for images inside the page, not the manuscript figure number.
- `PDF_NAME`.png: Image with thumbnails of every page with the figure and captions
  location for debugging.

Metadata:

```json
{
  "name": PDF_NAME,
  "xpdf_content_path": location for artifacts,
  "width": pdf width,
  "height": pdf height,
  "pages": [
    {
      "number": page number,
      "figures": [
        {
          "bbox": [x_top_left, y_top_left, width, height],
          "caption": figure caption,
          "name": figure name if any,
          "id": file name
        },
        ...
      ]
    },
    ...
  ]
}
```

## 3. Contribute

This project uses [Poetry](https://python-poetry.org/) for dependency management.
After cloning the repository, install the dependencies using ` poetry install`. For
VSCode, you can also add the environment to the project using and then installing
the dependencies:

```bash
poetry config virtualenvs.in-project true
peotry install
```

Then you can add the interpreter in your IDE. In case you need to delete and
reinstall an environment (.venv), check this [post](https://stackoverflow.com/a/64434542).

## 4. TODO

- Assumes that every page in the PDF has the same size
