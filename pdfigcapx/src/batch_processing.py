""" Batch processing of PDFs to extract figures and captions.
Use this script to process all the PDFs that are located in an input folder.

Run:
poetry run python pdfigcapx/src/batch_preprocessing.py 
    INPUT_FOLDER            -> folder with PDFs
    ARTIFACTS_FOLDER        -> folder to place processing artifacts
    OUTPUTS_FOLDER          -> folder where to place the outputs
    --no-individual-folders -> add to avoid creating a folder for every
                               PDF and instead put all the outputs in the OUTPUT FOLDER
    --num_workers           -> number of processors assigned to process in parallel
    --batch_size            -> number of documents to process before re-instantiating
                               a multiprocessing instance. Large numbers can 
                               flood the memory.
    --logs_path             -> folder to store logs, if NULL, same as OUTPUT FOLDER
    --reprocess-errors      -> add to reprocess PDFs marked as errors

The artifacts are PDF pages as images used to find the image and caption 
coordinates. They can be re-generated, but in case something goes wrong, 
reprocessing a PDF can re-read these artifacts and avoid re-creating them. We
recommend to set a temporary location for these elements.
"""


import logging
from typing import List
from argparse import Namespace
import argparse
import multiprocessing
from os import listdir, makedirs
from pathlib import Path
from src.document import Document


def process_pdf(
    pdf_path: str, xpdf_path: str, data_path: str, logs_path: str, create_folder: bool
):
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
    error_processing_path = Path(logs_path) / "pdfigcapx_failed.log"
    error_export_path = Path(logs_path) / "pdfigcapx_failed_export.log"
    error_draw_path = Path(logs_path) / "pdfigcapx_failed_draw.log"
    success_path = Path(logs_path) / "pdfigcapx_success.log"
    document_name = Path(pdf_path).stem

    try:
        print(pdf_path)
        # load the document data and identify the pages and regions
        target_path = data_path
        if create_folder:
            target_path = Path(data_path) / document_name
            makedirs(target_path, exist_ok=True)
        document = Document(pdf_path, xpdf_path, target_path, include_first_page=False)
        document.extract_figures()
    # pylint: disable=W0718:broad-exception-caught
    except Exception:
        logging.error(pdf_path, exc_info=True)
        with open(error_processing_path, "a", encoding="utf-8") as f_in:
            f_in.write(f"{document_name}\n")
        return

    try:
        # save the data to disk
        document.export_metadata(prefix=document_name)
        document.save_images(dpi=300, prefix=document_name)
    # pylint: disable=W0718:broad-exception-caught
    except Exception:
        logging.error(pdf_path, exc_info=True)
        with open(error_export_path, "a", encoding="utf-8") as f_in:
            f_in.write(f"{document_name}\n")
        return

    try:
        document.draw(n_cols=10, txtr=True, save=True)
    # pylint: disable=W0718:broad-exception-caught
    except Exception:
        logging.warning(pdf_path, exc_info=True)
        with open(error_draw_path, "a", encoding="utf-8") as f_in:
            f_in.write(f"{document_name}\n")

    with open(success_path, "a", encoding="utf-8") as f_in:
        f_in.write(f"{document_name}\n")


def filters_pdfs(ids: List[str], logs_path: str, reprocess_errors: bool) -> List[str]:
    """Get document names not processed before. Historical data is stored in
    failed_processing.log"""
    error_processing_path = Path(logs_path) / "pdfigcapx_failed.log"

    if not reprocess_errors and error_processing_path.exists():
        with open(error_processing_path, "r", encoding="utf-8") as f_in:
            failed_ids = f_in.readlines()
        failed_ids = [x.strip() for x in failed_ids]

        set_failed_ids = set(failed_ids)
        set_ids = set(ids)
        difference = set_ids.difference(set_failed_ids)
        return list(difference)
    return ids


def batch(iterable, n_items=256):
    """Create an iterable to process a long list in batches.
    Needed to process the data in batches and guarantee that we are not filling
    the memory with the data from processes that were already finished.
    """
    # https://stackoverflow.com/questions/8290397/how-to-split-an-iterable-in-constant-size-chunks
    l_items = len(iterable)
    for ndx in range(0, l_items, n_items):
        yield iterable[ndx : min(ndx + n_items, l_items)]


def parse_args():
    """Read command line arguments"""
    parser = argparse.ArgumentParser(
        prog="pdffigcapx",
        description="batch_processing",
    )
    parser.add_argument("inputs_path", help="location for inputs")
    parser.add_argument("xpdf_path", help="location for artifacts")
    parser.add_argument("outputs_path", help="location for outputs")
    parser.add_argument(
        "--no-individual-folders", dest="create_folders", action="store_false"
    )
    parser.set_defaults(create_folders=True)
    parser.add_argument("--num_workers", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--logs_path", type=str, default=None)
    parser.add_argument(
        "--reprocess-errors", dest="reprocess_errors", action="store_true"
    )
    parser.set_defaults(reprocess_errors=False)
    return parser.parse_args()


def setup_logging(args: Namespace, level=logging.INFO) -> Path:
    """Create logging folder and setting logging config"""
    logs_path = (
        Path(args.logs_path) if args.logs_path is not None else Path(args.outputs_path)
    )
    if not logs_path.exists():
        makedirs(logs_path, exist_ok=True)

    logfile_path = logs_path / "pdffigcapx.log"
    logging.basicConfig(
        filename=logfile_path.resolve(),
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=level,
    )
    return logs_path


if __name__ == "__main__":
    # Process every PDF inside an input folder
    cmd_args = parse_args()
    input_folder = Path(cmd_args.inputs_path)
    if not input_folder.exists():
        raise FileNotFoundError(f"Input folder {input_folder} does not exist")
    logging_path = setup_logging(cmd_args, level=logging.INFO)

    # Get pdf documents to process
    pdf_names = [el for el in listdir(input_folder) if el.endswith(".pdf")]
    pdfs_to_process = filters_pdfs(pdf_names, logging_path, cmd_args.reprocess_errors)
    # create tuples as entries for the multiprocessing starmap
    items = [
        (
            input_folder / el,
            cmd_args.xpdf_path,
            cmd_args.outputs_path,
            logging_path,
            cmd_args.create_folders,
        )
        for el in pdfs_to_process
    ]

    # Process data in batches to not collapse the system memory
    for data_batch in batch(items, n_items=cmd_args.batch_size):
        with multiprocessing.Pool(cmd_args.num_workers) as pool:
            pool.starmap(process_pdf, data_batch)
        pool.terminate()
