from typing import Dict, List

from youtube_transcript_api import YouTubeTranscriptApi, FetchedTranscript
from youtube_transcript_api.formatters import SRTFormatter

from app.utils import create_simple_logger


logger = create_simple_logger(__name__)

__all__ = [
    "get_transcript",
    "get_srt_transcript",
    "get_raw_transcript",
    "convert_ms_to_srt_time",
]


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
    video_id: str, languages: List[str] = ["en"], preserve_formatting: bool = True
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

    transcript = get_transcript(video_id, languages, preserve_formatting)
    formatter = SRTFormatter()
    transcript_formatted = formatter.format_transcript(transcript)
    logger.debug(f"Formatted transcript to SRT format for video ID: {video_id}")
    return transcript_formatted


def get_raw_transcript(
    video_id: str, languages: List[str] = ["en"], preserve_formatting: bool = True
) -> List[Dict[str, str | float]]:
    """Gets the raw transcript data of a YouTube video.

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
    list[dict]
        The raw transcript data as a list of dictionaries.
    """

    transcript = get_transcript(video_id, languages, preserve_formatting)
    logger.debug(f"Returning raw transcript data for video ID: {video_id}")
    return transcript.to_raw_data()


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
