from pathlib import Path
from typing import Optional
import subprocess

from .markdown_embedder import embed_images_reference_style
from app.utils import create_simple_logger


logger = create_simple_logger(__name__)


def _check_pandoc_installed() -> bool:
    """Check if pandoc is installed by trying to get its version."""
    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def convert_markdown_to_pdf(
    md_path: Path, pdf_path: Optional[Path] = None, remove_embedded_md: bool = True
) -> Path:
    embedded_md_path = md_path.with_suffix(".embedded.md")
    embed_images_reference_style(md_path, embedded_md_path)
    logger.info(
        f"Embedded images in markdown saved to {embedded_md_path}. Now converting to PDF."
    )

    if not _check_pandoc_installed():
        msg = (
            "Pandoc is not installed or not found in PATH. "
            "Please install pandoc to enable PDF conversion."
            "Otherwise, you can manually convert the embedded markdown to PDF using pandoc or after converting to HTML and using a browser print to PDF."
        )
        logger.error(msg)
        raise EnvironmentError(msg)

    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    pandoc_command = (
        f"LANG=C.UTF-8 LC_ALL=C.UTF-8 pandoc "
        f"--from=markdown+smart+emoji "
        "--pdf-engine-opt=-shell-escape "
        f"--pdf-engine=xelatex "
        f'"{embedded_md_path}" -o "{pdf_path}"'
    )
    result = subprocess.run(pandoc_command, shell=True)
    if result.returncode != 0:
        msg = f"Pandoc command failed with exit code {result.returncode}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(f"Converted markdown to PDF saved to {pdf_path}")
    if remove_embedded_md:
        try:
            embedded_md_path.unlink()
            logger.info(f"Removed temporary embedded markdown file {embedded_md_path}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {embedded_md_path}: {e}")
    return pdf_path
