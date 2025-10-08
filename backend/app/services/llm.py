from langchain_litellm import ChatLiteLLM
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import BaseMessage
from typing import List, AsyncGenerator, Dict, Optional, Union, Literal
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from app.utils import create_simple_logger

load_dotenv()
logger = create_simple_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

__all__ = [
    "create_llm_instance",
    "atext_completion",
    "atext_completion_stream",
    "acompletion_using_gemini",
    "acompletion_using_litellm",
    "acompletion_using_openai",
    "acompletion_using_openrouter",
    "acompletion_using_groq",
    "acompletion_using_ollama",
    "acompletion_using_nvidia",
]


def create_llm_instance(
    provider=Literal["google", "litellm", "openai", "openrouter", "groq", "ollama"],
    response_format: Optional[BaseModel] = None,
    model=LLM_MODEL,
    **kwargs: Dict,
) -> Union[ChatGoogleGenerativeAI, ChatLiteLLM, ChatOpenAI]:
    """Create and return an instance of the specified LLM runnable using provider and kwargs."""
    chat_runnable_mapping = {
        "google": ChatGoogleGenerativeAI,
        "litellm": ChatLiteLLM,
        "openai": ChatOpenAI,
        "openrouter": ChatOpenAI,
        "groq": ChatGroq,
        "ollama": ChatOllama,
        "nvidia": ChatNVIDIA,
    }

    if provider not in chat_runnable_mapping:
        raise ValueError(
            f"Unsupported provider: {provider}. Must be one of {list(chat_runnable_mapping.keys())}."
        )

    chat_runnable = chat_runnable_mapping[provider]
    logger.debug(f"Selected chat runnable: {chat_runnable.__name__}")

    to_remove = ["stream", "max_retries", "model"]
    for key in to_remove:
        if key in kwargs:
            kwargs.pop(key)

    if provider == "openrouter":
        # need to change API key and base URL for OpenRouter
        logger.debug("Configuring OpenRouter specific settings.")
        if "api_key" not in kwargs:
            kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")
        if "base_url" not in kwargs:
            kwargs["base_url"] = os.getenv(
                "OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"
            )
        if "default_headers" not in kwargs:
            kwargs["default_headers"] = {
                "HTTP-Referer": os.getenv("SITE_URL", "example.com"),
                "X-Title": os.getenv("SITE_NAME", "example.com"),
            }

    if provider == "ollama":
        logger.debug("Configuring Ollama specific settings.")
        if "api_key" not in kwargs:
            kwargs["api_key"] = os.getenv("OLLAMA_API_KEY")
        if "base_url" not in kwargs:
            kwargs["base_url"] = os.getenv(
                "OLLAMA_API_BASE", "http://localhost:11434/v1"
            )

    llm = chat_runnable(model=model, max_retries=3, **kwargs)

    if response_format:
        logger.debug("Applying structured output format.")
        llm = llm.with_structured_output(response_format)
    return llm


async def atext_completion(
    messages: List[BaseMessage],
    provider: Literal[
        "google", "litellm", "openai", "openrouter", "groq", "ollama", "nvidia"
    ] = "google",
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Return full (non-streaming) completion text asynchronously."""
    llm = create_llm_instance(
        provider=provider,
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
    provider: Literal["google", "litellm", "openai", "openrouter"] = "google",
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> AsyncGenerator[str, None]:
    """Async generator yielding incremental completion chunks without duplicates."""
    if "stream" not in kwargs:
        kwargs["stream"] = True
    llm = create_llm_instance(
        provider=provider,
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
        provider="google",
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
        provider="litellm",
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_openai(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for ChatOpenAI model completions."""
    return await atext_completion(
        messages=messages,
        provider="openai",
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
        provider="openrouter",
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_groq(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for Groq model completions."""
    return await atext_completion(
        messages=messages,
        provider="groq",
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_ollama(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for Ollama model completions."""
    return await atext_completion(
        messages=messages,
        provider="ollama",
        response_format=response_format,
        **kwargs,
    )


async def acompletion_using_nvidia(
    messages: List[BaseMessage],
    response_format: Optional[BaseModel] = None,
    **kwargs: Dict,
) -> str:
    """Helper function specifically for NVIDIA model completions."""
    return await atext_completion(
        messages=messages,
        provider="nvidia",
        response_format=response_format,
        **kwargs,
    )
