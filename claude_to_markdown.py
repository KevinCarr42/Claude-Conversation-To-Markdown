import json
import os
import glob
from pathlib import Path
from datetime import datetime


def load_jsonl_events(file_path):
    events = []
    with open(file_path, 'r', encoding='utf-8') as file_handle:
        for line in file_handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def format_timestamp(epoch_time):
    return datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')


def parse_filter_time(time_str):
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M').timestamp()
    except ValueError:
        return datetime.strptime(time_str, '%Y-%m-%d').timestamp()


def reconstruct_claude_history(project_directory, start_filter=None, end_filter=None):
    jsonl_files = list(Path(project_directory).rglob("*.jsonl"))

    main_thread_files = []
    subagent_threads = []

    start_ts = parse_filter_time(start_filter)
    end_ts = parse_filter_time(end_filter)

    for file_path in jsonl_files:
        thread_events = load_jsonl_events(file_path)
        if not thread_events:
            continue

        if any("subagent" in str(event).lower() for event in thread_events):
            subagent_threads.append(thread_events)
        else:
            main_thread_files.append(thread_events)

    all_reconstructed_conversations = []
    consumed_subagent_indices = set()

    for main_events in main_thread_files:
        main_events.sort(key=lambda x: x.get("created_at", 0))

        session_start = main_events[0].get("created_at", 0)
        if start_ts and session_start < start_ts:
            continue
        if end_ts and session_start > end_ts:
            continue

        unified_flow = []
        for event in main_events:
            unified_flow.append(event)
            event_text = str(event).lower()

            if "tool_use" in event_text and ("subagent" in event_text or "dispatch" in event_text):
                parent_timestamp = event.get("created_at", 0)
                best_match_index = -1
                min_drift = 2.0

                for index, sub_thread in enumerate(subagent_threads):
                    if index in consumed_subagent_indices:
                        continue

                    drift = abs(sub_thread[0].get("created_at", 0) - parent_timestamp)
                    if drift < min_drift:
                        min_drift = drift
                        best_match_index = index

                if best_match_index != -1:
                    unified_flow.extend(subagent_threads[best_match_index])
                    consumed_subagent_indices.add(best_match_index)

        unified_flow.sort(key=lambda x: x.get("created_at", 0))

        all_reconstructed_conversations.append({
            "session_metadata": {
                "start_time": format_timestamp(unified_flow[0].get("created_at", 0)),
                "end_time": format_timestamp(unified_flow[-1].get("created_at", 0)),
                "event_count": len(unified_flow)
            },
            "events": unified_flow
        })

    return all_reconstructed_conversations


def export_merged_log(project_path, output_filename, start_time=None, end_time=None):
    merged_sessions = reconstruct_claude_history(project_path, start_time, end_time)
    with open(output_filename, 'w', encoding='utf-8') as output_file:
        json.dump(merged_sessions, output_file, indent=2)


if __name__ == "__main__":
    output_directory = Path("output")
    output_filename = ("conversation_export.json")
    claude_code_conversation_path = Path("entire_conversation") / "projects_folder"

    output_directory.mkdir(parents=True, exist_ok=True)
    json_output_file = output_directory / output_filename

    export_merged_log(
        claude_code_conversation_path,
        json_output_file,
        start_time="2026-02-03 00:00",
        end_time="2026-02-03 09:00"
    )
