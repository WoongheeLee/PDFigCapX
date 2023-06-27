""" Batch processing for cases when the PDFs documents are each inside a folder.
Given an input folder, the script gets every folder inside (i.e., entry_folder) 
an processes the PDF located there. We assume that in this situation, the outputs
from the extraction should be located in the entry_folder.
An entry_folder is valid if there is only one PDF document inside.

run:
python src/batch_process_folders INPUT_PATH ARTIFACTS_PATH

"""

from os import cpu_count, makedirs
from sys import argv
from typing import List
from argparse import ArgumentParser, Namespace
from pathlib import Path
import logging
import multiprocessing
from src.utils import batch
from src.batch import process_pdf, setup_logging, ERROR_NO_PDF, ERROR_MORE_THAN_ONE_PDF


def parse_args(args) -> Namespace:
    """Read command line arguments"""
    parser = ArgumentParser(
        prog="pdffigcapx",
        description="batch processing one folder one doc",
    )
    parser.add_argument("input_path", type=str, help="root dir to folders to import")
    parser.add_argument("xpdf_path", type=str, help="artifacts folder")
    parser.add_argument("--num_workers", "-w", type=int, default=6)
    parser.add_argument("--logs_path", type=str, default=None)
    parser.add_argument("--batch_size", type=int, default=256)
    parsed_args = parser.parse_args(args)
    return parsed_args


def folder_exists(folder: Path):
    """Check if folder exists, if not, log error"""
    input_folder = Path(folder)
    if not input_folder.exists():
        message = f"Folder {input_folder} does not exist"
        logging.error(message)
        raise FileNotFoundError(input_folder)


def validate_inputs(args: Namespace) -> List[Path]:
    """Validate inpurt arguments.
    - Input and artifacts folders should exist
    - There should be only one PDF per folder, if not ignore those
    """
    input_folder = Path(args.input_path)
    folder_exists(input_folder)

    artifacts_folder = Path(args.xpdf_path)
    makedirs(artifacts_folder, exist_ok=True)

    folders = [
        elem
        for elem in input_folder.iterdir()
        if elem.is_dir() and not elem.name.startswith(".")
    ]
    pdf_paths = []
    folders_to_ignore = []
    for folder in folders:
        pdfs = [elem for elem in folder.iterdir() if elem.suffix.lower() == ".pdf"]
        if len(pdfs) == 0:
            logging.error("%s,%s", folder.name, ERROR_NO_PDF)
            folders_to_ignore.append(folder)
        elif len(pdfs) > 1:
            logging.error("%s,%s", folder.name, ERROR_MORE_THAN_ONE_PDF)
            folders_to_ignore.append(folder)
        else:
            pdf_paths.append(Path(folder) / pdfs[0])
    return pdf_paths


def main():
    """Entry point"""
    args = parse_args(argv[1:])
    logs_path = setup_logging(
        default_logs_dir=args.input_path,
        target_logs_dir=args.logs_path,
        level=logging.INFO,
    )
    num_workers = args.num_workers if args.num_workers < cpu_count() else cpu_count()

    # prepare arguments to save the data path into the input_path
    pdf_paths = validate_inputs(args)
    tuples = [
        (pdf_path, Path(args.xpdf_path), Path(pdf_path).parent, logs_path)
        for pdf_path in pdf_paths
    ]
    for data_batch in batch(tuples, n=args.batch_size):
        # process in batch so that the pool can terminate the forks
        # if not, the system can get overloaded of non-terminated processes
        with multiprocessing.Pool(num_workers) as pool:
            pool.starmap(process_pdf, data_batch)


if __name__ == "__main__":
    main()
