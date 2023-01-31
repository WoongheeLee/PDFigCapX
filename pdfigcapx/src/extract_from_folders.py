""" Batch processing for cases when there is one PDF document per folder"""

from os import argv, cpu_count
from typing import List
from argparse import ArgumentParser, Namespace
from pathlib import Path
import logging
import multiprocessing
from src.utils import batch
from src.document import Document

def setup_logger(workspace: str):
    """configure logger"""
    logger_dir = Path(workspace)
    if not logger_dir.exists:
        raise Exception("workspace does not exist")

    logging.basicConfig(
        filename=str(logger_dir / "pdfigcapx.log"),
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

def parse_args(args) -> Namespace:
    parser = ArgumentParser(
        prog="pdffigcapx",
        description="batch processing one folder one doc",
    )
    parser.add_argument("input_path", type=str, help="root dir to folders to import")
    parser.add_argument("xpdf_path", type=str, help="artifacts folder")
    parser.add_argument("--num_workers", "-w", type=int, default=6)
    parsed_args = parser.parse_args(args)

    return parsed_args

def folder_exists(folder: Path):
    input_folder = Path(folder)
    if not input_folder.exists():
        message = f"Folder {input_folder} does not exist"
        logging.error(message)
        raise Exception(message)

def validate_inputs(args: Namespace) -> List[Path]:
    """ Validate inpurt arguments.
    - Input and artifacts folders should exist
    - There should be only one PDF per folder, if not ignore those
    """
    input_folder = Path(args.input_path)
    artifacts_folder = Path(args.xpdf_path)
    folder_exists(input_folder)
    folder_exists(artifacts_folder)
        
    folders = [elem for elem in input_folder.iterdir() if elem.is_dir() and not elem.name.startswith(".")]
    folders_to_ignore = []
    for folder in folders:
        pdfs = [elem for elem in folder.iterdir() if elem.suffix.lower() == ".pdf"]
        if  len(pdfs) == 0:
            logging.info("%s,NO_PDF",folder.name)
            folders_to_ignore.append(folder)
        if len(pdfs) > 1:
            logging.info("%s,MORE_THAN_ONE_PDF",folder.name)
            folders_to_ignore.append(folder)
    return list(set(folders).difference(set(folders_to_ignore)))

def process_pdf(pdf_path: Path, xpdf_path: Path):
    """Process each PDF and extract data to data directory.
    Identifies the layout and extracts the figures per page. For bookkeeping, if
    the extraction fails, saves the document name to 'failed_processing.log'. If
    exporting the metadata or extracting the images fails, saves the document
    name to 'failed_export.log'. Finally, errors when drawing the debug figure
    are stored in 'failed_draw'; these last type of errors do not indicate a
    failure in processing and exporting. Use these logs to keep track of what
    has been processed and what errors to debug.
    Arguments:
    - pdf_path: Path
        Full path to the folder containing the pdf document
    - xpdf_path: Path
        Full path to folder where to save the xpdf content, which includes the pdf pages as HTML and PNG
    """
    data_path = pdf_path

    error_processing_path = Path(data_path).parent / "failed_processing.log"
    error_export_path = Path(data_path).parent / "failed_export.log"
    document_name = Path(pdf_path).stem

    try:
        print(pdf_path)
        # load the document data and identify the pages and regions
        document = Document(pdf_path, xpdf_path, pdf_path, include_first_page=False)
        document.extract_figures()
    except Exception:
        logging.info("%s,FAILED_EXTRACT", document_name)
        logging.error(f"{pdf_path}:", exc_info=True)
        with open(error_processing_path, "a") as f:
            f.write(f"{document_name}\n")
        return

    try:
        # save the data to disk
        document.export_metadata(prefix=document_name)
        document.save_images(dpi=300, prefix=document_name)
    except Exception:
        logging.info("%s,FAILED_EXPORT", document_name)
        logging.error(f"{pdf_path}:", exc_info=True)
        with open(error_export_path, "a") as f:
            f.write(f"{document_name}\n")


def main():
    args = parse_args(argv[1:])
    folders = validate_inputs(args)
    num_workers = args.num_workers if args.num_workers < cpu_count() else cpu_count()

    batch_size = 256
    # Process data in batches to not collapse the system memory
    tuples = [(folder, Path(args.xpdf_path)) for folder in folders]
    for data_batch in batch(tuples, n=batch_size):
        pool = multiprocessing.Pool()
        with multiprocessing.Pool(num_workers) as pool:
            pool.starmap(process_pdf, data_batch)
        pool.terminate()


if __name__ == "__main__":
    main()