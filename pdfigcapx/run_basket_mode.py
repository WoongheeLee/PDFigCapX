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

from sys import argv
import logging
from argparse import Namespace
from pathlib import Path
import argparse
from os import cpu_count
import pdfigcapx.batch_processing as bp


def parse_args(args) -> Namespace:
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
    parser.add_argument("--debug", dest="debug", action="store_true")
    parser.set_defaults(debug=False)
    return parser.parse_args(args)


def main():
    """Entry point"""
    args = parse_args(argv[1:])
    logs_path = bp.setup_logging(
        default_logs_dir=args.outputs_path,
        target_logs_dir=args.logs_path,
        level=logging.INFO,
    )
    if args.num_workers > cpu_count():
        args.num_workers = cpu_count()

    pdf_paths = bp.filter_basket_input(
        args.inputs_path, logs_path, args.reprocess_errors
    )
    artifacts_path = bp.check_artifacts_folder(args.xpdf_path)
    opts = {
        "num_workers": args.num_workers,
        "batch_size": args.batch_size,
        "debug": args.debug,
    }
    bp.process_in_basket_mode(
        pdf_paths,
        artifacts_path,
        Path(args.outputs_path),
        logs_path,
        args.create_folders,
        **opts
    )


if __name__ == "__main__":
    main()
