import os

file_dir = os.path.dirname(os.path.abspath(__file__))


def read_prompt_file(file_path: str) -> str:
    file_path = os.path.join(file_dir, file_path)
    with open(file_path, "r") as file:
        return file.read()


CHUNK_NOTES_SYSTEM_PROMPT = read_prompt_file("system_chunk_notes.txt")
FORMATTER_SYSTEM_PROMPT = read_prompt_file("system_formatter.txt")
NOTES_COLLECTOR_SYSTEM_PROMPT = read_prompt_file("system_notes_collector.txt")
SUMMARIZER_SYSTEM_PROMPT = read_prompt_file("system_summarizer.txt")
TIMESTAMP_GENERATOR_SYSTEM_PROMPT = read_prompt_file("system_timestamp_generator.txt")
IMAGE_INTEGRATOR_SYSTEM_PROMPT = read_prompt_file("system_image_integrator.txt")
