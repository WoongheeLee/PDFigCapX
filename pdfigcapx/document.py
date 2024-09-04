import logging
from os import listdir, makedirs
from pathlib import Path
from typing import List, Union
from math import ceil
from json import dumps as json_dumps
from shutil import rmtree
from matplotlib.pyplot import subplots, savefig, close as plt_close
from PIL import Image as PILImage

from pdfigcapx.models import Bbox, Figure, Layout
from pdfigcapx.page import HtmlPage
from pdfigcapx.utils import launch_chromedriver, extract_page_text_content, pdf2html
from pdfigcapx.draw import (
    draw_bboxes,
    draw_content_region,
    draw_text_regions,
    draw_columns,
)
import pdfigcapx.contours as cnt
from pdfigcapx.sweep import sweep_regions
import pdfigcapx.utils as utils
from pdfigcapx.layout import LayoutBuilder


def valid_file(filename: str):
    """Helper to filter only html files from pdf2html and not the index.html"""
    return filename.endswith(".html") and filename.startswith("page")


def valid_image(filename: str):
    """Helper to filter PNG images"""
    return filename.endswith(".png") and not filename.startswith(".")


class Document:
    """Represents a PDF document with every associated HTML page, figures,
    captions and bounding boxes
    """

    def __init__(
        self,
        pdf_path: str,
        xpdf_base_path: str,
        data_path: str,
        include_first_page=False,
    ):
        self.pdf_path = Path(pdf_path)
        self.doc_name = self.pdf_path.stem
        self.include_first_page = include_first_page
        self.xpdf_base_path = Path(xpdf_base_path)
        self.data_path = Path(data_path)

        self.pages: List[HtmlPage] = []
        self.layout: Layout = None

        logging.info(f"{self.doc_name} starting process ${self.pdf_path}")
        self.transform_pdf()
        self.fetch_pages()
        self.layout = LayoutBuilder.build(self.pages)
        # self.calculate_layout()
        self.expand_captions()

    def transform_pdf(self) -> None:
        """Converts the PDF to HTML using xpdf"""
        # print('START: transform_pdf')
        if not self.xpdf_base_path.exists():
            makedirs(self.xpdf_base_path)
        # print('self.xpdf_base_path', self.xpdf_base_path)

        prefixed_name = f"xpdf_{self.doc_name}"
        self.xpdf_path = self.xpdf_base_path / prefixed_name
        # print('self.xpdf_path', self.xpdf_path)
        if self.xpdf_path.exists():
            logging.debug(f"attempting to reuse xpdf content {self.xpdf_path}")
        else:
            print('self.xpdf_path not exists')
            print('self.pdf_path.resolve()', self.pdf_path.resolve())
            print('self.xpdf_base_path.resolve()', self.xpdf_base_path.resolve())
            print('prefixed_name', prefixed_name)
            out_path = pdf2html(
                self.pdf_path.resolve(), self.xpdf_base_path.resolve(), prefixed_name
            )
            # print('out_path', out_path)
            self.xpdf_path = Path(out_path)
            # print('self.xpdf_path', self.xpdf_path)

    def fetch_pages(self) -> None:
        """Parses the HTML pages using chromedriver to estimate sizes"""
        # print('START: fetch_pages')
        # print('self.xpdf_path', self.xpdf_path)
        names = [name for name in listdir(self.xpdf_path) if valid_file(name)]
        browser = launch_chromedriver()

        try:
            pages = []
            for page_name in names:
                page_path = (self.xpdf_path / page_name).resolve()
                page = extract_page_text_content(browser, page_path)
                pages.append(page)
        except Exception as error:
            logging.error("Error parsing pages", exc_info=True)
            raise Exception(error) from error
        finally:
            if browser:
                browser.quit()
        self.pages = sorted(pages, key=lambda x: x.number)

    def _log_no_captions_found(self):
        message = f"%s{self.doc_name}: no captions found"
        logging.info(message)

    def expand_captions(self):
        """Grab the starting caption, iterate over the text boxes not
        assigned as captions to expand the caption into a paragraph. Finally,
        estimate whether the caption spans over multiple columns or not.
        """
        for page in self.pages:
            page.expand_captions(self.layout)
        total_captions = sum([len(page.captions) for page in self.pages])
        if total_captions == 0:
            self._log_no_captions_found()

    def extract_figures(self, min_orphan_size=1000) -> None:
        """Traverse the pages in order and extract every figure by matching captions.
        When a page has captions and candidates, we have to match every caption.
        When a page only has candidates and no captions, the caption may be
          on the next page only if it's on the top of the page. In any other case,
          the candidate has no caption if the candidate size is big enough to
          represent a figure. Figures with no captions are common when the PDF
          includes supplementary material or when we missed to detect a caption
          pattern in a text box.
        """
        pages = []
        pages = self.pages if self.include_first_page else self.pages[1:]

        for idx, page in enumerate(pages):
            candidates, _, _ = cnt.get_candidates(
                str(self.xpdf_path), page, self.layout, page.captions
            )
            # match captions with candidates, assigned captions become figures
            if len(page.captions) > 0:
                if len(candidates) > 0:
                    sweep_regions(page, candidates, page.captions, [], self.layout)
                else:
                    self._log_captions_without_candidates(page)
                if page.orphan_figure is not None:
                    self._log_remaining_orphans_not_match(page)
            else:
                if len(candidates) > 0:
                    candidates = self._match_across_pages(
                        pages, idx, candidates, min_orphan_size
                    )
                    if candidates is not None:
                        # caption not found on next page, save as orphan image
                        bbox = Bbox.merge_bboxes(candidates)
                        figure = Figure(bbox, True, None, "orphan")
                        figure.identifier = ""
                        page.figures.append(figure)

    def _log_captions_without_candidates(self, page):
        message = f"{self.doc_name} - pg.{page.number}: captions have no candidates"
        logging.info(message)

    def _log_remaining_orphans_not_match(self, page):
        # pylint: disable-next=line-too-long
        message = f"{self.doc_name} - pg.{page.number}: remaining orphans not matched with any caption"
        logging.info(message)

    def _match_across_pages(
        self,
        pages: List[HtmlPage],
        page_idx: int,
        candidates: List[Bbox],
        min_orphan_size: int,
    ) -> List[Bbox]:
        if page_idx == len(pages) - 1:
            # last page can't have caption on next page
            return candidates
        bbox = Bbox.merge_bboxes(candidates)
        if bbox.area() < min_orphan_size:
            # candidates too small, discard
            return None
        # grab captions that are just below the content region
        thres = self.layout.content_region.x + self.layout.row_height * 1.5
        captions = [c for c in pages[page_idx + 1].captions if c.x < thres]
        if len(captions) != 1:
            # no captions or too many, which idk how to handle
            return candidates

        orphan_caption = captions[0]
        # update captions on next page by reference
        updated_captions = [
            c for c in pages[page_idx + 1].captions if c.id != orphan_caption.id
        ]
        pages[page_idx + 1].captions = updated_captions
        figure = Figure(bbox, True, orphan_caption, "orphan")
        figure.identifier = captions[0].get_caption_identifier()
        pages[page_idx].figures.append(figure)
        # assigned orphan figure to caption in next page succesfully
        return None

    def draw(
        self,
        n_cols: int,
        cr=True,
        txtr=False,
        colr=False,
        capr=True,
        figr=True,
        save=False,
    ) -> None:
        """Draw the extracted content for all pages on a canvas for debugging purposes"""
        n_rows = ceil(len(self.pages) / n_cols)
        fig, ax = subplots(n_rows, n_cols, dpi=300)

        for idx, page in enumerate(self.pages):
            col = idx % n_cols
            row = int(idx / n_cols)

            page_name = page.img_name
            png_path = (self.xpdf_path / page_name).resolve()
            page_image = PILImage.open(png_path)
            page_image = page_image.resize((page.width, page.height))

            if cr:
                draw_content_region(ax[row][col], self.layout.content_region)
            if txtr:
                draw_text_regions(ax[row][col], page)
            if colr:
                draw_columns(ax[row][col], self.layout)
            if capr:
                draw_bboxes(ax[row][col], page.captions, "black", "black", 1.0)
            if figr:
                bboxes = [el.bbox for el in page.figures]
                draw_bboxes(ax[row][col], bboxes, "orange", "orange", 0.7)
            ax[row][col].imshow(page_image)
            ax[row][col].set_title(f"pg.{page.number}")
            ax[row][col].axis("off")
        for idx in range(len(self.pages), n_rows * n_cols):
            col = idx % n_cols
            row = int(idx / n_cols)
            ax[row][col].axis("off")
        fig.suptitle(self.pdf_path.stem)
        fig.tight_layout()

        if save:
            if not self.data_path.exists():
                makedirs(self.data_path.resolve())
            output_path = self.data_path / f"{self.doc_name}.png"
            savefig(output_path, dpi=1200)
        plt_close(fig)  # close to avoid memory leak

    def _fetch_pages_as_images(self, dpi=300) -> list[PILImage.Image]:
        """Return PDF pages as PIL Images"""
        output_folder = self.data_path / f"{self.doc_name}_images"
        makedirs(output_folder, exist_ok=True)
        utils.pdf2images(self.pdf_path.resolve(), output_folder.resolve(), dpi=dpi)
        filenames = listdir(output_folder)
        image_names = [x for x in filenames if valid_image(x)]
        image_names = utils.natural_sort(image_names)
        images = []
        for image_name in image_names:
            pil_image = PILImage.open(output_folder / image_name).convert("RGB")
            pil_image.load()  # load into memory (also closes the file associated)
            images.append(pil_image)
        rmtree(output_folder)
        return images

    def _fig_name(self, prefix: Union[str, None], page: HtmlPage, fig_idx: int) -> str:
        """naming convention for saving figure data"""
        str_prefix = "" if not prefix else f"{prefix}_"
        name = f"{str_prefix}{page.number}_{fig_idx+1}.jpg"
        return name

    # 원래 코드
    # def save_images(self, dpi=300, prefix=None):
    #     """Save extracted images to disk"""
    #     pil_images = self._fetch_pages_as_images(dpi)
    #     for page, pil_image in zip(self.pages, pil_images):
    #         scale = float(pil_image.size[0]) / self.layout.width

    #         for idx, fig in enumerate(page.figures):
    #             crop_box = [
    #                 fig.bbox.x * scale,
    #                 fig.bbox.y * scale,
    #                 fig.bbox.x1 * scale,
    #                 fig.bbox.y1 * scale,
    #             ]
    #             extracted_fig = pil_image.crop(crop_box)
    #             fig_name = self._fig_name(prefix, page, idx)
    #             fig_path = self.data_path / fig_name
    #             extracted_fig.save(fig_path)
    #             extracted_fig.close()

    # 몇 퍼 더 키운거
    def save_images(self, dpi=300, prefix=None, scale_percentage=3.5):
        """Save extracted images to disk"""
        pil_images = self._fetch_pages_as_images(dpi)
        for page, pil_image in zip(self.pages, pil_images):
            scale = float(pil_image.size[0]) / self.layout.width

            for idx, fig in enumerate(page.figures):
                # 원래 좌표
                x0 = fig.bbox.x * scale
                y0 = fig.bbox.y * scale
                x1 = fig.bbox.x1 * scale
                y1 = fig.bbox.y1 * scale

                # 너비 높이
                width = x1 - x0
                height = y1 - y0

                # 비율 계산
                delta_w = width * (scale_percentage / 100.)
                delta_h = height * (scale_percentage / 100.)

                # 조정 좌표
                crop_box = [
                    x0 - delta_w,
                    y0 - delta_h,
                    x1 + delta_w,
                    y1 + delta_h,
                ]

                extracted_fig = pil_image.crop(crop_box)
                fig_name = self._fig_name(prefix, page, idx)
                fig_path = self.data_path / fig_name
                extracted_fig.save(fig_path)
                extracted_fig.close()

    def export_metadata(self, prefix: None):
        """Export extracted metadata to disk"""
        export_content = {
            "name": self.doc_name,
            "xpdf_content_path": str(self.xpdf_base_path),
            "width": self.layout.width,
            "height": self.layout.height,
            "pages": [],
        }

        for page in self.pages:
            if len(page.figures) > 0:
                page_content = {"number": page.number, "figures": []}
                for fig_idx, figure in enumerate(page.figures):
                    page_content["figures"].append(
                        {
                            "bbox": figure.bbox.to_arr(),
                            "caption": figure.caption.text if figure.caption else "",
                            "name": figure.identifier,
                            "id": self._fig_name(prefix, page, fig_idx),
                        }
                    )
                export_content["pages"].append(page_content)

        export_json = json_dumps(export_content, indent=2)
        output_path = self.data_path / f"{self.doc_name}.json"
        with open(output_path, "w", encoding="utf-8") as outfile:
            outfile.write(export_json)

    def debug_candidates(self, n_cols=10):
        """Plot the extracted contours detected from graphical content"""
        n_rows = ceil(len(self.pages) / n_cols)
        fig, ax = subplots(n_rows, n_cols, dpi=300)
        pages = []
        pages = self.pages if self.include_first_page else self.pages[1:]

        for idx, page in enumerate(pages):
            candidates, cnts, orig_cnts = cnt.get_candidates(
                str(self.xpdf_path), page, self.layout, page.captions
            )
            col = idx % n_cols
            row = int(idx / n_cols)

            page_name = page.img_name
            png_path = (self.xpdf_path / page_name).resolve()
            page_image = PILImage.open(png_path)
            page_image = page_image.resize((page.width, page.height))

            page_box = Bbox(1, 1, page.width, page.height)
            draw_bboxes(ax[row][col], [page_box], "black", "none", 1.0)
            draw_content_region(ax[row][col], self.layout.content_region)
            draw_bboxes(ax[row][col], page.captions, "black", "black", 0.5)
            draw_bboxes(ax[row][col], candidates, "red", "red", 0.5)
            draw_bboxes(ax[row][col], cnts, "blue", "blue", 0.5)
            draw_bboxes(ax[row][col], orig_cnts, "green", "green", 0.5)
            ax[row][col].imshow(page_image)
            ax[row][col].set_title(f"pg.{page.number}")
            ax[row][col].axis("off")

        # TODO: do i need to close the fig to avoid memory leaking?
        for idx in range(len(self.pages), n_rows * n_cols):
            col = idx % n_cols
            row = int(idx / n_cols)
            ax[row][col].axis("off")
