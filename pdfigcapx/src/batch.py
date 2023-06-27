""" Logic to execute when processing an input document """

from os import makedirs
from pathlib import Path
import logging
from typing import Optional
from src.document import Document

ERROR_NO_PDF = "NO_PDF"
ERROR_MORE_THAN_ONE_PDF = "MORE_THAN_ONE_PDF"


def process_pdf(
    pdf_path: str,
    xpdf_path: str,
    data_path: str,
    logs_path: str,
    create_folder: bool = False,
    debug=True,
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
