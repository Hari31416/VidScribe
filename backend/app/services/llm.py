from langchain_litellm import ChatLiteLLM
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAI
from langchain_core.messages import BaseMessage
from typing import List, Any, AsyncGenerator, Dict, Optional, Union
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from app.utils import create_simple_logger

load_dotenv()
logger = create_simple_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

__all__ = [
    "atext_completion",
    "atext_completion_stream",
    "acompletion_using_gemini",
    "acompletion_using_litellm",
    "acompletion_using_openai",
    "acompletion_using_openrouter",
]


def _create_llm_instance(
    chat_runnable: Union[ChatGoogleGenerativeAI, ChatLiteLLM, OpenAI],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> Union[ChatGoogleGenerativeAI, ChatLiteLLM, OpenAI]:
    """Create and return an instance of the specified LLM runnable."""
    if "model" not in kwargs:
        kwargs["model"] = LLM_MODEL

    to_remove = ["stream", "max_retries"]
    for key in to_remove:
        if key in kwargs:
            kwargs.pop(key)

    llm = chat_runnable(max_retries=3, **kwargs)

    if response_format:
        logger.debug("Applying structured output format.")
        llm = llm.with_structured_output(response_format)
    return llm


async def atext_completion(
    messages: List[BaseMessage],
    chat_runnable: Union[
        ChatGoogleGenerativeAI, ChatLiteLLM, OpenAI
    ] = ChatGoogleGenerativeAI,
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Return full (non-streaming) completion text asynchronously.
    messages: list of {role, content}
    """
    llm = _create_llm_instance(
        chat_runnable=chat_runnable,
        response_format=response_format,
        **kwargs,
    )

    try:
        res = await llm.ainvoke(messages)
    except Exception as e:
        logger.error(f"Error during async completion: {e}")
        raise e

    if response_format:
        try:
            return res.model_dump()
        except Exception as e:
            logger.warning(f"Error during model_dump: {e}\nReturning raw response.")
            return str(res)

    if hasattr(res, "text"):
        return res.text()
    return str(res)


async def atext_completion_stream(
    messages: List[BaseMessage],
    chat_runnable: Union[
        ChatGoogleGenerativeAI, ChatLiteLLM, OpenAI
    ] = ChatGoogleGenerativeAI,
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> AsyncGenerator[str, None]:
    """Async generator yielding incremental completion chunks without duplicates."""
    if "stream" not in kwargs:
        kwargs["stream"] = True
    llm = _create_llm_instance(
        chat_runnable=chat_runnable,
        response_format=response_format,
        **kwargs,
    )

    try:
        response_stream = llm.astream(messages)
    except Exception as e:
        logger.error(f"Error during async streaming completion: {e}")
        raise e

    assembled = ""
    async for chunk in response_stream:
        if response_format:
            try:
                assembled = chunk.model_dump()
                yield assembled
            except Exception as e:
                logger.warning(f"Error during model_dump: {e}\nYielding raw chunk.")
                yield str(chunk)
        else:
            if hasattr(chunk, "text"):
                text_chunk = chunk.text()
            else:
                text_chunk = str(chunk)
            # Yield only new text to avoid duplicates
            if text_chunk.startswith(assembled):
                new_text = text_chunk[len(assembled) :]
                if new_text:
                    yield new_text
                    assembled += new_text
            else:
                # In case of unexpected change, yield the whole chunk
                yield text_chunk
                assembled = text_chunk


async def acompletion_using_gemini(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for Gemini model completions."""
    return await atext_completion(
        messages=messages,
        chat_runnable=ChatGoogleGenerativeAI,
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_litellm(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for LiteLLM model completions."""
    return await atext_completion(
        messages=messages,
        chat_runnable=ChatLiteLLM,
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_openai(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for OpenAI model completions."""
    return await atext_completion(
        messages=messages,
        chat_runnable=OpenAI,
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_openrouter(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for OpenRouter model completions."""
    return await atext_completion(
        messages=messages,
        chat_runnable=OpenAI,
        response_format=response_format,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
        default_headers={
            "HTTP-Referer": os.getenv("YOUR_SITE_URL", "example.com"),
            "X-Title": os.getenv("YOUR_SITE_NAME", "example.com"),
        },
        **kwargs,
    )
