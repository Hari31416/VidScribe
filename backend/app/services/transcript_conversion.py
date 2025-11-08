from datetime import datetime


def vtt_to_srt(vtt_content):
    srt_content = ""
    lines = vtt_content.splitlines()
    index = 1
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_time, end_time = line.split(" --> ")
            start_time = start_time.replace(".", ",")
            end_time = end_time.replace(".", ",")
            srt_content += f"{index}\n{start_time} --> {end_time}\n"
            index += 1
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                srt_content += lines[i] + "\n"
                i += 1
            srt_content += "\n"
        i += 1

    return srt_content


def srt_to_youtube_json(srt_content):
    entries = srt_content.strip().split("\n\n")
    transcript = []

    for entry in entries:
        lines = entry.split("\n")
        if len(lines) >= 3:
            time_range = lines[1]
            text = " ".join(lines[2:])

            start_str, end_str = time_range.split(" --> ")
            start_time = datetime.strptime(start_str, "%H:%M:%S,%f")
            end_time = datetime.strptime(end_str, "%H:%M:%S,%f")

            start_seconds = (start_time - datetime(1900, 1, 1)).total_seconds()
            end_seconds = (end_time - datetime(1900, 1, 1)).total_seconds()

            transcript.append(
                {
                    "text": text,
                    "start": start_seconds,
                    "duration": round(end_seconds - start_seconds, 3),
                }
            )

    return transcript


def vtt_to_youtube_json(vtt_content):
    srt_content = vtt_to_srt(vtt_content)
    youtube_json = srt_to_youtube_json(srt_content)
    return youtube_json
