from pathlib import Path
from typing import Optional
import os
import platform
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


def _check_xelatex_installed() -> bool:
    """Check if xelatex is installed by trying to get its version."""
    try:
        result = subprocess.run(
            ["xelatex", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def convert_markdown_to_pdf(
    md_path: Path,
    pdf_path: Optional[Path] = None,
    remove_embedded_md: bool = True,
    preamble: Optional[str] = None,
) -> Path:
    embedded_md_path = md_path.with_suffix(".embedded.md")
    embed_images_reference_style(md_path, embedded_md_path, preamble=preamble)
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

    if not _check_xelatex_installed():
        system = platform.system().lower()
        if system == "darwin":  # macOS
            msg = (
                "XeLaTeX is not installed or not found in PATH. "
                "Please install MacTeX (full LaTeX distribution):\n"
                "1. brew install mactex\n"
                "2. Or download from: https://www.tug.org/mactex/\n"
                "3. After installation, restart your terminal or run: source ~/.zshrc\n"
                "Note: MacTeX is large (~4GB), consider mactex-no-gui for smaller install"
            )
        elif system == "linux":
            msg = (
                "XeLaTeX is not installed or not found in PATH. "
                "Please install TeX Live with XeLaTeX:\n"
                "1. Ubuntu/Debian: sudo apt update && sudo apt install texlive-xetex texlive-fonts-recommended\n"
                "2. CentOS/RHEL: sudo yum install texlive-xetex\n"
                "3. Arch: sudo pacman -S texlive-xetex"
            )
        else:  # Windows or other
            msg = (
                "XeLaTeX is not installed or not found in PATH. "
                "Please install a LaTeX distribution:\n"
                "1. MiKTeX: https://miktex.org/download\n"
                "2. TeX Live: https://www.tug.org/texlive/"
            )
        logger.error(msg)
        raise EnvironmentError(msg)

    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    # Build pandoc command as a list for better cross-platform compatibility
    pandoc_cmd = [
        "pandoc",
        "--from=markdown+smart+emoji",
        "--pdf-engine=xelatex",
        "--pdf-engine-opt=-shell-escape",
        # Add macOS-specific options if needed
        "--variable",
        "geometry:margin=1in",
        "--variable",
        "fontsize=11pt",
        str(embedded_md_path),
        "-o",
        str(pdf_path),
    ]

    # Set environment variables for consistent behavior across platforms
    env = os.environ.copy()
    env.update({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})

    logger.info(f"Running pandoc command: {' '.join(pandoc_cmd)}")

    try:
        result = subprocess.run(
            pandoc_cmd, env=env, capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            error_msg = f"Pandoc command failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\nStderr: {result.stderr}"
            if result.stdout:
                error_msg += f"\nStdout: {result.stdout}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    except FileNotFoundError as e:
        system = platform.system().lower()
        if system == "darwin":  # macOS
            msg = (
                "Pandoc or xelatex not found. Please ensure both are installed and in PATH:\n"
                "1. Install pandoc: brew install pandoc\n"
                "2. Install MacTeX: brew install mactex\n"
                "3. After installation, restart your terminal or run: source ~/.zshrc\n"
                "4. Check PATH: echo $PATH | grep -E '(pandoc|mactex|texlive)'\n"
                f"Error: {e}"
            )
        elif system == "linux":
            msg = (
                "Pandoc or xelatex not found. Please ensure both are installed:\n"
                "1. Install pandoc: sudo apt install pandoc\n"
                "2. Install xelatex: sudo apt install texlive-xetex texlive-fonts-recommended\n"
                f"Error: {e}"
            )
        else:
            msg = (
                "Pandoc or xelatex not found. Please ensure both are installed and in PATH.\n"
                f"Error: {e}"
            )
        logger.error(msg)
        raise EnvironmentError(msg) from e
    except Exception as e:
        msg = f"Unexpected error during PDF conversion: {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    logger.info(f"Converted markdown to PDF saved to {pdf_path}")
    if remove_embedded_md:
        try:
            embedded_md_path.unlink()
            logger.info(f"Removed temporary embedded markdown file {embedded_md_path}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {embedded_md_path}: {e}")
    return pdf_path
