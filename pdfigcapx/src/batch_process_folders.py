""" Run batch processing in INPUT_FOLDER mode
Batch processing for cases when the PDFs documents are each inside a folder.
Given an input folder, the script gets every folder inside (i.e., entry_folder) 
an processes the PDF located there. We assume that in this situation, the outputs
from the extraction should be located in the entry_folder.
An entry_folder is valid if there is only one PDF document inside.

run:
python src/batch_process_folders INPUT_PATH ARTIFACTS_PATH

"""

from os import cpu_count
from sys import argv
from argparse import ArgumentParser, Namespace
import logging
import src.batch_processing as bp


def parse_args(args) -> Namespace:
    """Read command line arguments"""
    parser = ArgumentParser(
        prog="pdffigcapx",
        description="batch processing in folder mode: one folder one PDF",
    )
    parser.add_argument("input_path", type=str, help="root dir to folders to import")
    parser.add_argument("xpdf_path", type=str, help="artifacts folder")
    parser.add_argument("--logs_path", type=str, default=None)
    parser.add_argument("--num_workers", "-w", type=int, default=6)
    parser.add_argument("--batch_size", type=int, default=256)
    parsed_args = parser.parse_args(args)
    return parsed_args


def main():
    """Entry point"""
    args = parse_args(argv[1:])
    logs_path = bp.setup_logging(
        default_logs_dir=args.input_path,
        target_logs_dir=args.logs_path,
        level=logging.INFO,
    )
    num_workers = args.num_workers if args.num_workers < cpu_count() else cpu_count()
    artifacts_path = bp.check_artifacts_folder(args.xpdf_path)
    pdf_paths = bp.filter_folder_input(args)
    bp.process_in_folder_mode(
        pdf_paths, artifacts_path, logs_path, args.batch_size, num_workers
    )


if __name__ == "__main__":
    main()
