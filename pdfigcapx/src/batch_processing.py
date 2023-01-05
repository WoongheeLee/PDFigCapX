import logging
import argparse
import multiprocessing
from os import listdir
from pathlib import Path
from src.document import Document
from typing import List

"""
poetry run python src/batch_processing.py /home/jtt/Documents/datasets/gxd /home/jtt/Documents/outputs/xpdf /home/jtt/Documents/outputs/gdx
"""


def process_pdf(pdf_path: str, xpdf_path: str, data_path: str):
    """Process each PDF and extract data to data directory.
    Identifies the layout and extracts the figures per page. For bookkeeping, if
    the extraction fails, saves the document name to 'failed_processing.log'. If
    exporting the metadata or extracting the images fails, saves the document
    name to 'failed_export.log'. Finally, errors when drawing the debug figure
    are stored in 'failed_draw'; these last type of errors do not indicate a
    failure in processing and exporting. Use these logs to keep track of what
    has been processed and what errors to debug.
    Arguments:
    - pdf_path: str
        Full path to the PDF document
    - xpdf_path: str
        Full path to folder where to save the xpdf content, which includes the pdf pages as HTML and PNG
    - data_path: str
        Full path to folder where to save the extracted images and metadata information
    """
    error_processing_path = Path(data_path) / "failed_processing.log"
    error_export_path = Path(data_path) / "failed_export.log"
    error_draw_path = Path(data_path) / "failed_draw.log"
    document_name = Path(pdf_path).stem

    try:
        print(pdf_path)
        # load the document data and identify the pages and regions
        document = Document(pdf_path, xpdf_path, data_path, include_first_page=False)
        document.extract_figures()
    except Exception:
        logging.error(f"{pdf_path}:", exc_info=True)
        with open(error_processing_path, "a") as f:
            f.write(f"{document_name}\n")
        return

    try:
        # save the data to disk
        document.export_metadata(prefix=document_name)
        document.save_images(dpi=300, prefix=document_name)
    except Exception:
        logging.error(f"{pdf_path}:", exc_info=True)
        with open(error_export_path, "a") as f:
            f.write(f"{document_name}\n")

    try:
        document.draw(n_cols=10, txtr=True, save=True)
    except Exception:
        logging.warning(f"{pdf_path}:", exc_info=True)
        with open(error_draw_path, "a") as f:
            f.write(f"{document_name}\n")


def filter_not_processed(ids: List[str], logs_path: str) -> List[str]:
    """Get document names not processed before. Historical data is stored in
    failed_processing.log"""
    error_processing_path = Path(logs_path) / "failed_processing.log"

    with open(error_processing_path, "r") as f:
        failed_ids = f.readlines()
    failed_ids = [x.strip() for x in failed_ids]

    set_failed_ids = set(failed_ids)
    set_ids = set(ids)
    difference = set_ids.difference(set_failed_ids)
    return list(difference)


def batch(iterable, n=256):
    """Create an iterable to process a long list in batches.
    Needed to process the data in batches and guarantee that we are not filling
    the memory with the data from processes that were already finished.
    """
    # https://stackoverflow.com/questions/8290397/how-to-split-an-iterable-in-constant-size-chunks
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx : min(ndx + n, l)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="pdffigcapx",
        description="batch_processing",
    )
    parser.add_argument("pdfs_path")
    parser.add_argument("xpdf_path")
    parser.add_argument("data_path")
    parser.add_argument("--num_workers", type=int, default=10)
    args = parser.parse_args()

    input_folder = Path(args.pdfs_path)
    if not input_folder.exists():
        raise Exception(f"Input folder {input_folder} does not exist")

    log_path = Path(args.data_path) / "pdfigcapx.log"
    logging.basicConfig(
        filename=log_path.resolve(),
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    # Get pdf documents to process
    pdf_names = [el for el in listdir(input_folder) if el.endswith(".pdf")]
    pdfs_to_process = filter_not_processed(pdf_names, args.data_path)
    batch_size = 256
    items = [
        (input_folder / el, args.xpdf_path, args.data_path) for el in pdfs_to_process
    ]

    # Process data in batches to not collapse the system memory
    for data_batch in batch(items, n=batch_size):
        pool = multiprocessing.Pool()
        with multiprocessing.Pool(args.num_workers) as pool:
            pool.starmap(process_pdf, data_batch)
        pool.terminate()
