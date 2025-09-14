from typing import Dict, List, Optional
import tiktoken

from app.utils import create_simple_logger


logger = create_simple_logger(__name__)

__all__ = [
    "chunk_transcript_by_max_tokens",
    "chunk_transcript_by_num_chunks",
    "chunk_transcript",
]


def chunk_transcript_by_max_tokens(
    transcript: List[Dict[str, str | float]],
    max_tokens: int,
    overlap_items: int = 5,
) -> List[List[Dict[str, str | float]]]:
    """
    Chunks a transcript into smaller segments based on a maximum token limit.

    Parameters
    ----------
    transcript : List[Dict[str, str|float]]
        The transcript to be chunked, where each entry is a dictionary containing 'text' and other metadata.
    max_tokens : int
        The maximum number of tokens allowed in each chunk.
    overlap_items : int, optional
        The number of overlapping items to include between chunks, by default 5.

    Returns
    -------
    List[List[Dict[str, str|float]]]
        A list of transcript chunks, where each chunk is a list of transcript entries.
    """
    chunks = []
    current_chunk = []
    current_token_count = 0

    for entry in transcript:
        text = entry["text"]
        tokens = tiktoken.get_encoding("cl100k_base").encode(text)
        token_count = len(tokens)

        if current_token_count + token_count > max_tokens and current_chunk:
            chunks.append(current_chunk)
            # Start new chunk with overlap
            current_chunk = (
                current_chunk[-overlap_items:]
                if overlap_items < len(current_chunk)
                else current_chunk[:]
            )
            current_token_count = sum(
                len(tiktoken.get_encoding("cl100k_base").encode(e["text"]))
                for e in current_chunk
            )

        current_chunk.append(entry)
        current_token_count += token_count

    if current_chunk:
        chunks.append(current_chunk)
    logger.info(f"Chunked transcript into {len(chunks)} segments based on max tokens.")
    return chunks


def chunk_transcript_by_num_chunks(
    transcript: List[Dict[str, str | float]],
    num_chunks: int,
    overlap_items: int = 5,
    show_avg_tokens: bool = False,
) -> List[List[Dict[str, str | float]]]:
    """
    Chunks a transcript into a specified number of segments.

    Parameters
    ----------
    transcript : List[Dict[str, str|float]]
        The transcript to be chunked, where each entry is a dictionary containing 'text' and other metadata.
    num_chunks : int
        The desired number of chunks to split the transcript into.
    overlap_items : int, optional
        The number of overlapping items to include between chunks, by default 5.

    Returns
    -------
    List[List[Dict[str, str|float]]]
        A list of transcript chunks, where each chunk is a list of transcript entries.
    """
    total_entries = len(transcript)
    if num_chunks <= 0 or total_entries == 0:
        return []

    if num_chunks == 1:
        return [transcript]

    if num_chunks > total_entries:
        num_chunks = total_entries
        logger.warning(
            f"Requested number of chunks exceeds total entries. Reducing num_chunks to {total_entries}."
        )

    avg_chunk_size = total_entries // num_chunks
    chunks = []
    start_index = 0

    for i in range(num_chunks):
        end_index = start_index + avg_chunk_size
        if i == num_chunks - 1:  # Last chunk takes the remainder
            end_index = total_entries

        chunk = transcript[start_index:end_index]
        chunks.append(chunk)

        # Move start index for next chunk with overlap
        start_index = end_index - overlap_items
        if start_index < 0:
            start_index = 0

        if start_index >= total_entries:
            break

    if show_avg_tokens:
        avg_tokens_per_chunk = sum(
            len(tiktoken.get_encoding("cl100k_base").encode(entry["text"]))
            for chunk in chunks
            for entry in chunk
        ) / len(chunks)
        logger.info(f"Average tokens per chunk: {int(avg_tokens_per_chunk)}")

    return chunks


def chunk_transcript(
    transcript: List[Dict[str, str | float]],
    max_tokens: Optional[int] = None,
    num_chunks: Optional[int] = None,
    overlap_items: int = 5,
    show_avg_tokens: bool = False,
) -> List[List[Dict[str, str | float]]]:
    """
    Chunks a transcript into segments based on either a maximum token limit or a specified number of chunks.

    Parameters
    ----------
    transcript : List[Dict[str, str|float]]
        The transcript to be chunked, where each entry is a dictionary containing 'text' and other metadata.
    max_tokens : int, optional
        The maximum number of tokens allowed in each chunk. If provided, this takes precedence over num_chunks.
    num_chunks : int, optional
        The desired number of chunks to split the transcript into. Ignored if max_tokens is provided.
    overlap_items : int, optional
        The number of overlapping items to include between chunks, by default 5.
    show_avg_tokens : bool, optional
        Whether to log the average number of tokens per chunk, by default False.

    Returns
    -------
    List[List[Dict[str, str|float]]]
        A list of transcript chunks, where each chunk is a list of transcript entries.
    """

    if max_tokens is None and num_chunks is None:
        msg = "Either max_tokens or num_chunks must be provided."
        logger.error(msg)
        raise ValueError(msg)

    if max_tokens is not None and num_chunks is not None:
        logger.warning(
            "Both max_tokens and num_chunks provided. max_tokens will take precedence."
        )

    if max_tokens is not None:
        return chunk_transcript_by_max_tokens(transcript, max_tokens, overlap_items)
    else:
        return chunk_transcript_by_num_chunks(
            transcript, num_chunks or 1, overlap_items, show_avg_tokens
        )
