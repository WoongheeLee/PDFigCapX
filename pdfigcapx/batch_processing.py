""" Logic to execute when processing an input document.
The batch imports support two modes FOLDER_INPUT and FOLDER_BASKET.
- FOLDER_INPUT: The input_path contains folders where each folder contains the 
                PDF document to import
- FOLDER_BASKET: The input_path contains PDF documents
"""

from os import makedirs
from pathlib import Path
import logging
import multiprocessing
from typing import Optional, List
from pdfigcapx.utils import batch
from pdfigcapx.document import Document

ERROR_NO_PDF = "NO_PDF"
ERROR_MORE_THAN_ONE_PDF = "MORE_THAN_ONE_PDF"
FAILED_LOG = "pdfigcapx_failed.log"


def process_pdf(
    pdf_path: str,
    xpdf_path: str,
    data_path: str,
    logs_path: str,
    create_folder: bool = False,
    debug: bool = True,
) -> None:
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
    error_processing_path = Path(logs_path) / FAILED_LOG
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
        logging.error("%s,FAILED_EXTRACT", document_name, exc_info=True)
        with open(error_processing_path, "a", encoding="utf-8") as f_in:
            f_in.write(f"{document_name}\n")
        return

    try:
        # save the data to disk
        document.export_metadata(prefix=document_name)
        document.save_images(dpi=300, prefix=document_name)
    # pylint: disable=W0718:broad-exception-caught
    except Exception:
        logging.error("%s,FAILED_EXPORT", document_name, exc_info=True)
        logging.error(pdf_path, exc_info=True)
        with open(error_export_path, "a", encoding="utf-8") as f_in:
            f_in.write(f"{document_name}\n")
        return

    if debug:
        try:
            document.draw(n_cols=10, txtr=True, save=True)
        # pylint: disable=W0718:broad-exception-caught
        except Exception:
            logging.warning("%s,FAILED_DRAW", document_name, exc_info=True)
            with open(error_draw_path, "a", encoding="utf-8") as f_in:
                f_in.write(f"{document_name}\n")

    with open(success_path, "a", encoding="utf-8") as f_in:
        f_in.write(f"{document_name}\n")


def setup_logging(
    default_logs_dir: str,
    target_logs_dir: Optional[str] = None,
    level=logging.INFO,
    log_name="pdffigcapx.log",
) -> Path:
    """configure logger"""
    logger_path = Path(default_logs_dir)
    if target_logs_dir is not None:
        logger_path = Path(target_logs_dir)

    if not logger_path.exists():
        makedirs(logger_path, exist_ok=True)

    logging.basicConfig(
        filename=str(logger_path / log_name),
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=level,
    )
    return logger_path


def check_artifacts_folder(artifacts_dir: str) -> Path:
    """Create artifacts path is it does not exist"""
    artifacts_path = Path(artifacts_dir)
    makedirs(artifacts_path, exist_ok=True)
    return artifacts_path


def filter_folder_input(inputs_dir: str) -> List[Path]:
    """When importing in FOLDER_INPUT mode, filter out any folder that does not
    contains only one PDF inside.
    Arguments
    -----------
    - inputs_dir: str
        Root folder to the folders containing the PDFs to process
    Output
    -----------
    - List of valid pdf Paths
    Exceptions
    -----------
    - FileNotFoundError if input_dir does not exist
    """
    in_path = Path(inputs_dir)
    if not in_path.exists():
        logging.error("input directory does not exist")
        raise FileNotFoundError(in_path)

    folders = [
        el for el in in_path.iterdir() if el.is_dir() and not el.name.startswith(".")
    ]
    valid_pdf_paths = []
    for folder in folders:
        pdfs = [el for el in folder.iterdir() if el.suffix.lower() == ".pdf"]
        if len(pdfs) == 0:
            logging.error("%s,%s", folder.name, ERROR_NO_PDF)
        elif len(pdfs) > 1:
            logging.error("%s,%s", folder.name, ERROR_MORE_THAN_ONE_PDF)
        else:
            valid_pdf_paths.append(Path(folder) / pdfs[0])
    return valid_pdf_paths


def filter_basket_input(
    inputs_dir: str, logs_path: str, reprocess_errors: bool
) -> List[Path]:
    """When importing in BASKET_MODE, filter out any PDFs to avoid reprocessing
    TODO: not considering the case when a document in the log gets processed and
    needs to be removed from that list
    """
    in_path = Path(inputs_dir)
    if not in_path.exists():
        logging.error("input directory does not exist")
        raise FileNotFoundError(in_path)

    error_processing_path = Path(logs_path) / FAILED_LOG
    in_pdfs = [el for el in in_path.iterdir() if el.suffix.lower() == ".pdf"]

    if not reprocess_errors and error_processing_path.exists():
        with open(error_processing_path, "r", encoding="utf-8") as f_in:
            failed_ids = f_in.readlines()
        failed_ids = [x.strip() for x in failed_ids]

        set_failed_ids = set(failed_ids)
        set_ids = set(in_pdfs)
        difference = set_ids.difference(set_failed_ids)
        in_pdfs = list(difference)
    return [in_path / pdf for pdf in in_pdfs]


def process_in_folder_mode(
    pdf_paths: List[Path],
    artifacts_path: Path,
    logs_path: Path,
    batch_size: int = 256,
    num_workers: int = 6,
    debug: bool = False,
) -> None:
    """Process the list of PDFs in batches to avoid overload the system with
    OS forks."""
    in_tuples = [
        (pdf_path, artifacts_path, pdf_path.parent, logs_path, False, debug)
        for pdf_path in pdf_paths
    ]

    for data_batch in batch(in_tuples, n=batch_size):
        with multiprocessing.Pool(num_workers) as pool:
            pool.starmap(process_pdf, data_batch)


def process_in_basket_mode(
    pdf_paths: List[Path],
    artifacts_path: Path,
    outputs_path: Path,
    logs_path: Path,
    create_folder: bool,
    batch_size: int = 256,
    num_workers: int = 6,
    debug: bool = False,
) -> None:
    """Process the list of PDFs in batches to avoid overload the system with
    OS forks."""
    in_tuples = [
        (pdf_path, artifacts_path, outputs_path, logs_path, create_folder, debug)
        for pdf_path in pdf_paths
    ]

    for data_batch in batch(in_tuples, n=batch_size):
        with multiprocessing.Pool(num_workers) as pool:
            pool.starmap(process_pdf, data_batch)
