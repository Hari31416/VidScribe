import os
from typing import Optional, Tuple

import ffmpeg
from PIL import Image

from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

file_dir = os.path.dirname(os.path.abspath(__file__))
# move two levels up to reach the 'backend' directory
backend_dir = os.path.abspath(os.path.join(file_dir, "../.."))
downloads_dir = os.path.join(backend_dir, "outputs", "frames")
os.makedirs(downloads_dir, exist_ok=True)
logger.debug(f"Image downloads directory set at: {downloads_dir}")

DEFAULT_IMAGE_SHAPE = (720, 1280)  # 720p


def _get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds."""
    try:
        probe = ffmpeg.probe(video_path)
        duration = float(probe["format"]["duration"])
        logger.debug(f"Video duration of {video_path}: {duration} seconds")
        return duration
    except ffmpeg.Error as e:
        logger.error(f"Error getting video duration: {e.stderr.decode()}")
        raise RuntimeError(f"Could not get video duration for {video_path}") from e


def _raise_timestamp_if_exceeds_duration(timestamp: str, duration: float) -> None:
    """Raise an error if the given timestamp exceeds the video duration."""
    h, m, s = map(int, timestamp.split(":"))
    total_seconds = h * 3600 + m * 60 + s
    if total_seconds > duration:
        raise ValueError(
            f"Timestamp {timestamp} exceeds video duration of {duration} seconds."
        )


def _extract_frame(video_path, timestamp, output_path, verbose=False):
    """Extract a single frame from a video at a specific timestamp."""
    duration = _get_video_duration(video_path)
    _raise_timestamp_if_exceeds_duration(timestamp, duration)
    (
        ffmpeg.input(video_path, ss=timestamp)
        .output(output_path, vframes=1, loglevel="error")
        .run(overwrite_output=True, quiet=not verbose)
    )
    logger.debug(f"Frame extracted at {timestamp} and saved to {output_path}")
    return output_path


def add_duration_to_timestamp(timestamp: str, quantity: int, unit: str) -> str:
    """Add a duration to a timestamp string in "HH:MM:SS" format.

    Parameters
    ----------
    timestamp : str
        The original timestamp in "HH:MM:SS" format.
    quantity : int
        The quantity of the duration to add.
    unit : str
        The unit of the duration ('seconds', 'minutes', 'hours').

    Returns
    -------
    str
        The new timestamp after adding the duration, in "HH:MM:SS" format.
    """
    h, m, s = map(int, timestamp.split(":"))
    total_seconds = h * 3600 + m * 60 + s

    if unit == "seconds":
        total_seconds += quantity
    elif unit == "minutes":
        total_seconds += quantity * 60
    elif unit == "hours":
        total_seconds += quantity * 3600
    else:
        raise ValueError("Unit must be 'seconds', 'minutes', or 'hours'.")

    new_h = total_seconds // 3600
    new_m = (total_seconds % 3600) // 60
    new_s = total_seconds % 60

    new_timestamp = f"{new_h:02}:{new_m:02}:{new_s:02}"
    logger.debug(f"Timestamp {timestamp} + {quantity} {unit} = {new_timestamp}")
    return new_timestamp


def extract_frame(
    video_path: str,
    timestamp: str,
    output_dir: str = downloads_dir,
    image_shape: tuple[int, int] = DEFAULT_IMAGE_SHAPE,
    video_id: Optional[str] = None,
    verbose: bool = False,
) -> Tuple[str, Image.Image]:
    """Extract a frame from a video at a specific timestamp and save it as an image.

    Parameters
    ----------
    video_path : str
        Path to the input video file.
    timestamp : str
        Timestamp in the format "HH:MM:SS" to extract the frame.
    output_path : str
        Path to save the extracted image.
    image_shape : tuple[int, int], optional
        Desired image shape as (height, width). Default is (720, 1280).
    video_id : Optional[str], optional
        Optional video ID to use in naming the output file. If None, derived from video_path.
    verbose : bool, optional
        If True, enables verbose logging. Default is False.

    Returns
    -------
    Tuple[str, Image.Image]
        A tuple containing the path to the saved image and the PIL Image object.
    """
    if video_id is None:
        video_id = video_path.split(os.path.sep)[-2]
        logger.info(f"Video ID not provided. Derived ID from path as: {video_id}")

    output_dir = os.path.join(output_dir, video_id)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir, f"frame_at_{timestamp.replace(':', '-')}.jpg"
    )

    _extract_frame(video_path, timestamp, output_path, verbose=verbose)

    img = Image.open(output_path)
    if img.size != (image_shape[1], image_shape[0]):  # PIL uses (width, height)
        img = img.resize((image_shape[1], image_shape[0]))
        img.save(output_path)
        logger.debug(f"Resized image to {image_shape} and saved to {output_path}")
    else:
        logger.debug(
            f"Image size matches desired shape {image_shape}. No resize needed."
        )
    return output_path, img


# TODO: Check for duplicate frames
