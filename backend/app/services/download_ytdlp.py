import os
from typing import Dict, Any, Optional

import yt_dlp

from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

file_dir = os.path.dirname(os.path.abspath(__file__))
# move two levels up to reach the 'backend' directory
backend_dir = os.path.abspath(os.path.join(file_dir, "../.."))
downloads_dir = os.path.join(backend_dir, "outputs", "videos")
os.makedirs(downloads_dir, exist_ok=True)
logger.debug(f"Video downloads directory set at: {downloads_dir}")


def _video_format_for_resolution(resolution: Optional[int]) -> str:
    """Build a yt_dlp format selector that prefers MP4/M4A and caps height.

    Examples:
      - resolution=720 -> best video up to 720p merged with best audio, else best up to 720p
    """
    cap = f"height<=?{resolution}" if resolution else "height<=?2160"
    # Prefer mp4 video and m4a audio when merging; fallback to best single file at or below cap
    return (
        f"((bestvideo[{cap}][ext=mp4]/bestvideo[{cap}])+(bestaudio[ext=m4a]/bestaudio))/"
        f"best[{cap}]"
    )


def _video_only_format_for_resolution(resolution: Optional[int]) -> str:
    """Selector for video-only streams (no audio), preferring MP4 container when possible."""
    cap = f"height<=?{resolution}" if resolution else "height<=?2160"
    return f"bestvideo[{cap}][ext=mp4]/bestvideo[{cap}]"


def download_media(
    video_id: str,
    *,
    resolution: Optional[int] = None,
    audio_only: bool = False,
    video_only: bool = False,
    audio_format: str = "mp3",
    output_dir: str = downloads_dir,
    filename_template: str = "%(title)s.%(ext)s",
    verbose: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Download a YouTube video or extract audio using yt_dlp.

    Parameters
    ----------
    video_id : str
        The YouTube video ID or URL to download.
    resolution : Optional[int], optional
        The maximum video resolution (height in pixels) to download. If None, no limit is applied.
    audio_only : bool, optional
        If True, only download audio and convert to the specified audio_format.
    video_only : bool, optional
        If True, download only the video stream (no audio) using a video-only format.
    audio_format : str, optional
        The audio format to convert to if audio_only is True. Default is 'mp3'.
    output_dir : str, optional
        The directory where downloaded files will be saved. Default is 'outputs/videos' in the backend directory.
    filename_template : str, optional
        The template for naming downloaded files. Default is '%(title)s.%(ext)s'.
    verbose : bool, optional
        If True, yt_dlp will output more detailed logs. Default is False.
    overwrite : bool, optional
        If True, existing files in the output directory may be overwritten. Default is False.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the status of the download, titles of downloaded items,
        number of items, and list of downloaded file paths.
    """
    if video_id.startswith("http"):
        video_id = video_id.split("v=")[-1].split("&")[0]

    if not output_dir.endswith(video_id):
        output_dir = os.path.join(output_dir, video_id)

    if os.path.exists(output_dir):
        files_in_dir = os.listdir(output_dir)
        if files_in_dir:
            logger.info(
                f"Output directory {output_dir} already exists and is not empty. "
                "Files may be overwritten."
            )
    os.makedirs(output_dir, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts: Dict[str, Any] = {
        # Put all files under the provided output_dir regardless of playlist or single
        "paths": {"home": output_dir},
        "outtmpl": filename_template,
        "restrictfilenames": True,
        "noprogress": False,
        "quiet": not verbose,
        "merge_output_format": "mp4",  # when merging video+audio
    }

    if audio_only and video_only:
        raise ValueError("audio_only and video_only cannot both be True")

    if audio_only:
        ydl_opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": audio_format,
                        "preferredquality": "0",
                    }
                ],
            }
        )
    elif video_only:
        ydl_opts.update({"format": _video_only_format_for_resolution(resolution)})
    else:
        ydl_opts.update({"format": _video_format_for_resolution(resolution)})

    result: Dict[str, Any] = {
        "status": "unknown",
        "url": url,
        "output_dir": os.path.abspath(output_dir),
        "audio_only": audio_only,
        "video_only": video_only,
        "resolution": resolution,
        "downloaded_files": [],
    }

    def _hook(d: Dict[str, Any]):
        if d.get("status") == "finished":
            filename = d.get("filename")
            if filename and filename not in result["downloaded_files"]:
                result["downloaded_files"].append(filename)

    ydl_opts.setdefault("progress_hooks", []).append(_hook)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_probe = ydl.extract_info(url, download=False)
            if "entries" in info_probe and isinstance(info_probe["entries"], list):
                entries_probe = [e for e in info_probe["entries"] if e]
            else:
                entries_probe = [info_probe]

            # Compute expected filenames using the same template and options
            expected_files = []
            titles = []
            for e in entries_probe:
                try:
                    raw_path = ydl.prepare_filename(e)
                except Exception:
                    # Fallback to simple title-based path if prepare_filename fails
                    safe_title = str(e.get("title", "video")).replace(os.sep, "_")
                    raw_path = os.path.join(output_dir, f"{safe_title}.temp")

                if audio_only:
                    base, _ = os.path.splitext(raw_path)
                    expected = f"{base}.{audio_format}"
                elif video_only:
                    # Keep original prepared filename (video-only ext)
                    expected = raw_path
                else:
                    base, _ = os.path.splitext(raw_path)
                    final_ext = ydl_opts.get("merge_output_format", "mp4")
                    expected = f"{base}.{final_ext}"
                expected_files.append(expected)
                titles.append(str(e.get("title")))

            if (
                not overwrite
                and expected_files
                and all(os.path.exists(p) for p in expected_files)
            ):
                logger.info(
                    "Skipping download; files already exist and overwrite=False"
                )
                result.update(
                    {
                        "status": "skipped",
                        "titles": titles,
                        "count": len(entries_probe),
                        "downloaded_files": expected_files,
                    }
                )
                return result

            info = ydl.extract_info(url, download=True)
            # Normalize playlist vs single
            if "entries" in info and isinstance(info["entries"], list):
                entries = [e for e in info["entries"] if e]
                titles = [str(e.get("title")) for e in entries]
            else:
                entries = [info]
                titles = [str(info.get("title"))]

            result.update(
                {
                    "status": "success",
                    "titles": titles,
                    "count": len(entries),
                }
            )
    except yt_dlp.utils.DownloadError as e:
        result.update({"status": "error", "error": str(e)})
    except Exception as e:  # pylint: disable=broad-except
        result.update({"status": "error", "error": str(e)})

    return result


def download_thumbnail(
    video_id: str, output_dir: str = downloads_dir, verbose: bool = False
) -> Dict[str, Any]:
    """Download the thumbnail of a YouTube video using yt_dlp.

    Parameters
    ----------
    video_id : str
        The YouTube video ID or URL to download the thumbnail from.
    output_dir : str, optional
        The directory where the downloaded thumbnail will be saved. Default is 'outputs/videos' in the backend directory.
    verbose : bool, optional
        If True, yt_dlp will output more detailed logs. Default is False.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the status of the download, title of the video,
        and the path to the downloaded thumbnail file.
    """

    if video_id.startswith("http"):
        video_id = video_id.split("v=")[-1].split("&")[0]

    if not output_dir.endswith(video_id):
        output_dir = os.path.join(output_dir, video_id)

    if os.path.exists(output_dir):
        files_in_dir = os.listdir(output_dir)
        if files_in_dir:
            logger.info(
                f"Output directory {output_dir} already exists and is not empty. "
                "Files may be overwritten."
            )
    os.makedirs(output_dir, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts: Dict[str, Any] = {
        # Put all files under the provided output_dir regardless of playlist or single
        "paths": {"home": output_dir},
        "outtmpl": "%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noprogress": False,
        "quiet": not verbose,
        "skip_download": True,  # We only want to download the thumbnail
        "writethumbnail": True,  # Instruct yt_dlp to download the thumbnail
    }

    result: Dict[str, Any] = {
        "status": "unknown",
        "url": url,
        "output_dir": os.path.abspath(output_dir),
        "thumbnail_file": None,
    }

    def _hook(d: Dict[str, Any]):
        if d.get("status") == "finished" and d.get("info_dict", {}).get("thumbnail"):
            thumbnail_url = d["info_dict"]["thumbnail"]
            title = d["info_dict"].get("title", "unknown_title")
            ext = thumbnail_url.split(".")[-1].split("?")[
                0
            ]  # Handle URLs with query params
            safe_title = str(title).replace(os.sep, "_")
            filename = os.path.join(output_dir, f"{safe_title}.{ext}")
            result["thumbnail_file"] = filename

    ydl_opts.setdefault("progress_hooks", []).append(_hook)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_probe = ydl.extract_info(url, download=False)
            title = str(info_probe.get("title", "unknown_title"))

            # Compute expected thumbnail filename using the same template and options
            thumbnail_url = info_probe.get("thumbnail")
            if thumbnail_url:
                ext = thumbnail_url.split(".")[-1].split("?")[
                    0
                ]  # Handle URLs with query params
                safe_title = title.replace(os.sep, "_")
                expected_thumbnail = os.path.join(output_dir, f"{safe_title}.{ext}")
            else:
                expected_thumbnail = None

            if expected_thumbnail and os.path.exists(expected_thumbnail):
                logger.info("Skipping thumbnail download; file already exists.")
                result.update(
                    {
                        "status": "skipped",
                        "title": title,
                        "thumbnail_file": expected_thumbnail,
                    }
                )
                return result
            info = ydl.extract_info(url, download=True)
            result.update(
                {
                    "status": "success",
                    "title": title,
                }
            )
    except yt_dlp.utils.DownloadError as e:
        result.update({"status": "error", "error": str(e)})
    except Exception as e:  # pylint: disable=broad-except
        result.update({"status": "error", "error": str(e)})
    return result
