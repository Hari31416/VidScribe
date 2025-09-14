from langgraph.runtime import Runtime
from typing_extensions import TypedDict
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class RuntimeState(TypedDict):
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    video_id: str
