"""
Transcript Processing Nodes for VidScribe.

Handles fetching and processing video transcripts from:
- YouTube Transcript API (for YouTube videos)
- Local files
- MinIO storage (for user-uploaded transcripts)
"""

from typing import Dict, List, Optional
import os
import json

from youtube_transcript_api import YouTubeTranscriptApi, FetchedTranscript
from youtube_transcript_api.formatters import SRTFormatter

from app.utils import create_simple_logger


logger = create_simple_logger(__name__)
cur_file_dir = os.path.dirname(os.path.abspath(__file__))
# move three levels up to reach the 'backend' directory
backend_dir = os.path.abspath(os.path.join(cur_file_dir, "../../../"))
outputs_dir = os.path.join(backend_dir, "outputs")
transcript_dir = os.path.join(outputs_dir, "transcripts")
os.makedirs(transcript_dir, exist_ok=True)

AVG_TOKENS_PER_TRANSCRIPT_ENTRY = 9

__all__ = [
    "get_transcript",
    "get_srt_transcript",
    "get_raw_transcript",
    "get_raw_transcript_from_storage",
    "convert_ms_to_srt_time",
    "extract_text_from_transcript_chunk",
]


def transcript_file_path(video_id: str, file_extension: str = "srt") -> str:
    """Generates the file path for storing the transcript of a YouTube video.

    Parameters
    ----------
    video_id : str
        The YouTube video ID.
    file_extension : str, optional
        The file extension for the transcript file, by default "srt"

    Returns
    -------
    str
        The full file path for the transcript file.
    """
    filename = f"{video_id}.{file_extension}"
    return os.path.join(transcript_dir, filename)


def get_transcript(
    video_id: str, languages: List[str] = ["en"], preserve_formatting: bool = True
) -> FetchedTranscript:
    """Gets the transcript of a YouTube video as a FetchedTranscript object.

    Parameters
    ----------
    video_id : str
        The YouTube video ID.
    languages : list[str], optional
        List of language codes to try, by default ["en"]
    preserve_formatting : bool, optional
        Whether to preserve formatting, by default True

    Returns
    -------
    FetchedTranscript
        The transcript as a FetchedTranscript object.
    """

    ytt_api = YouTubeTranscriptApi()
    transcript = ytt_api.fetch(
        video_id, languages=languages, preserve_formatting=preserve_formatting
    )
    logger.info(f"Fetched {len(transcript)} transcripts for video ID: {video_id}")
    return transcript


def get_srt_transcript(
    video_id: str,
    languages: List[str] = ["en"],
    preserve_formatting: bool = True,
    overwrite: bool = False,
) -> str:
    """Gets the transcript of a YouTube video in SRT format.

    Parameters
    ----------
    video_id : str
        The YouTube video ID.
    languages : list[str], optional
        List of language codes to try, by default ["en"]
    preserve_formatting : bool, optional
        Whether to preserve formatting, by default True

    Returns
    -------
    str
        The transcript in SRT format.
    """
    transcript_file = transcript_file_path(video_id, "srt")
    if os.path.exists(transcript_file) and not overwrite:
        with open(transcript_file, "r", encoding="utf-8") as file:
            srt_content = file.read()
            logger.info(f"Loaded cached SRT transcript for video ID: {video_id}")
            return srt_content

    transcript = get_transcript(video_id, languages, preserve_formatting)
    formatter = SRTFormatter()
    transcript_formatted = formatter.format_transcript(transcript)
    logger.debug(f"Formatted transcript to SRT format for video ID: {video_id}")
    with open(transcript_file, "w", encoding="utf-8") as file:
        file.write(transcript_formatted)
        logger.info(f"Saved SRT transcript to {transcript_file}")
    return transcript_formatted


def get_raw_transcript_from_storage(
    username: str,
    project_id: str,
) -> List[Dict[str, str | float]]:
    """Gets the raw transcript data from MinIO storage.

    Parameters
    ----------
    username : str
        The username who owns the project
    project_id : str
        The project ID

    Returns
    -------
    list[dict]
        The raw transcript data as a list of dictionaries.
    """
    from app.services.storage_service import get_storage_service

    storage = get_storage_service()

    try:
        transcript_bytes = storage.get_transcript(username, project_id)
        if transcript_bytes is None:
            raise ValueError(f"Transcript not found for project '{project_id}'")

        transcript_data = json.loads(transcript_bytes.decode("utf-8"))
        logger.info(
            f"Loaded transcript from MinIO for user '{username}', project '{project_id}'"
        )
        return transcript_data
    except Exception as e:
        logger.error(f"Failed to load transcript from MinIO: {e}")
        raise


def get_raw_transcript(
    video_id: str,
    languages: List[str] = ["en"],
    preserve_formatting: bool = True,
    overwrite: bool = False,
    username: Optional[str] = None,
) -> List[Dict[str, str | float]]:
    """Gets the raw transcript data of a YouTube video or from storage.

    If username is provided, tries to fetch from MinIO storage first.
    Falls back to local cache or YouTube API.

    Parameters
    ----------
    video_id : str
        The YouTube video ID or project ID.
    languages : list[str], optional
        List of language codes to try, by default ["en"]
    preserve_formatting : bool, optional
        Whether to preserve formatting, by default True
    overwrite : bool, optional
        Whether to overwrite cached data, by default False
    username : str, optional
        If provided, fetches from MinIO storage instead of YouTube

    Returns
    -------
    list[dict]
        The raw transcript data as a list of dictionaries.
    """
    # Try MinIO storage first if username is provided
    if username:
        try:
            return get_raw_transcript_from_storage(username, video_id)
        except Exception as e:
            logger.warning(f"Could not load from MinIO, trying local/YouTube: {e}")

    # Fall back to local cache
    raw_file = transcript_file_path(video_id, "json")
    if os.path.exists(raw_file) and not overwrite:
        with open(raw_file, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
            logger.info(f"Loaded cached raw transcript for video ID: {video_id}")
            return raw_data

    # Check if this is a known local project ID pattern
    if video_id.startswith(("transcript_", "upload_", "proj_")):
        error_msg = (
            f"Project ID '{video_id}' appears to be local, but transcript was not found in storage. "
            "Aborting YouTube API fetch."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Fetch from YouTube API
    transcript = get_transcript(video_id, languages, preserve_formatting)
    logger.debug(f"Returning raw transcript data for video ID: {video_id}")
    data = transcript.to_raw_data()
    with open(raw_file, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(f"Saved raw transcript to {raw_file}")
    return data


def convert_ms_to_srt_time(milliseconds: float) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm).

    Parameters
    ----------
    milliseconds : float
        Time in milliseconds.

    Returns
    -------
    str
        Time in SRT format.
    """
    hours = int(milliseconds // 3600000)
    minutes = int((milliseconds % 3600000) // 60000)
    seconds = int((milliseconds % 60000) // 1000)
    millis = int(milliseconds % 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def extract_text_from_transcript_chunk(
    transcript_chunk: List[Dict[str, str | float]], add_timestamps: bool = True
) -> str:
    """
    Extracts and concatenates text from a chunk of transcript entries.

    Parameters
    ----------
    transcript_chunk : List[Dict[str, str|float]]
        A chunk of the transcript, where each entry is a dictionary containing 'text' and other metadata.
    add_timestamps : bool, optional
        Whether to prepend timestamps to each text entry, by default True.

    Returns
    -------
    str
        The concatenated text from the transcript chunk.
    """
    final_text = ""
    for entry in transcript_chunk:
        text = entry.get("text", "")
        if add_timestamps:
            time = convert_ms_to_srt_time(int(entry.get("start", 0) * 1000))
            final_text += f"[{time}] {text}\n"
        else:
            final_text += f"{text} "
    return final_text.strip()
