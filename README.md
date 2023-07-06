# PdfFigCapX

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

### 1.3 Install the pip package

```bash
pip install "git+https://github.com/jtrells/PDFigCapX.git#egg=pdfigcapx"
```

## 2. Usage

We provide two scripts to batch process input PDFs based on the inputs configuration:

- `INPUT_FOLDER` mode: The input location contains folders where each folder includes a PDF document to process. The outputs are located inside each folder.
- `INPUT_BASKET` mode: The input location contains the PDFs documents. You can configure where to store the outputs.

### 2.1 Run in `INPUT_FOLDER` mode

```bash
cd pdfigcapx
poetry run python pdfigcapx/run_folder_mode.py INPUT_FOLDER ARTIFACTS_FOLDER --logs_path LOGS_PATH --num_workers 6 --batch_size 256 --debug
```

Parameters:

- INPUT_FOLDER: path to folder containing the folders to process
- ARTIFACTS_FOLDER: path to folder for storing xpdf outputs
- logs_path (optional): path to store logs, if not provided, uses INPUT_FOLDER
- num_workers (optional): number of processors to allocate
- batch_size (optional): number of processes to allocate in the pool per batch
- debug (optional): create an image with all bounding boxes for debugging

### 2.2 Run in `INPUT_BASKET` mode

Process every PDF and create a folder per PDF with the images and captions inside `OUTPUT_FOLDER`:

```bash
cd pdfigcapx
poetry run python pdfigcapx/run_basket_mode.py INPUT_FOLDER ARTIFACTS_FOLDER OUTPUT_FOLDER --logs_path LOGS_FOLDER --num_workers 10
```

Optional parameters:

- no-individual-folders: add to avoid creating one folder per PDF and instead
  add all the outputs to the `OUTPUT_FOLDER`
- reprocess-errors: add to reprocess any PDF that generated a processing error
  on a previous run
- logs_path: If not specified, uses the `OUTPUT_FOLDER`

### 2.3 Run in Docker

The Dockfile uses an ubuntu image with Python 3.10 and installs every pre-requisite.
To install the image use:

```bash
docker build -t pdfigcapx:0.1.0 .
docker run -ti --rm -v INPUT_FOLDER:/mnt pdfigcapx:0.1.0 /bin/bash
# inside docker
cd /workspace/PDFigCapX
# run script as shown in 2.1 or 2.2
```

The Dockerfile has hardcoded the latest chromedriver and xpdf tools available
at the moment of this commit. However, check whether there are more recent versions
available and update the Dockerfile accordingly.

## 2.3 Outputs

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
