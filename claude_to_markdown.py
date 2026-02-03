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


def parse_iso_timestamp(iso_str):
    """Convert ISO timestamp string to epoch time."""
    if not iso_str:
        return 0
    try:
        # Handle ISO format with Z suffix
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0


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

        # Check if this is a subagent file by looking at the path or agentId field
        is_subagent = ('subagents' in str(file_path) or
                       any('agentId' in event for event in thread_events))

        if is_subagent:
            subagent_threads.append(thread_events)
        else:
            main_thread_files.append(thread_events)

    all_reconstructed_conversations = []
    consumed_subagent_indices = set()

    for main_events in main_thread_files:
        # Convert ISO timestamps to epoch and sort
        for event in main_events:
            event['_epoch_timestamp'] = parse_iso_timestamp(event.get("timestamp"))

        main_events.sort(key=lambda x: x.get("_epoch_timestamp", 0))

        session_start = main_events[0].get("_epoch_timestamp", 0)
        if start_ts and session_start < start_ts:
            continue
        if end_ts and session_start > end_ts:
            continue

        unified_flow = []
        for event in main_events:
            unified_flow.append(event)
            event_text = str(event).lower()

            if "tool_use" in event_text and ("subagent" in event_text or "dispatch" in event_text):
                parent_timestamp = event.get("_epoch_timestamp", 0)
                best_match_index = -1
                min_drift = 2.0

                for index, sub_thread in enumerate(subagent_threads):
                    if index in consumed_subagent_indices:
                        continue

                    # Ensure subagent threads also have epoch timestamps
                    if '_epoch_timestamp' not in sub_thread[0]:
                        for sub_event in sub_thread:
                            sub_event['_epoch_timestamp'] = parse_iso_timestamp(sub_event.get("timestamp"))

                    drift = abs(sub_thread[0].get("_epoch_timestamp", 0) - parent_timestamp)
                    if drift < min_drift:
                        min_drift = drift
                        best_match_index = index

                if best_match_index != -1:
                    unified_flow.extend(subagent_threads[best_match_index])
                    consumed_subagent_indices.add(best_match_index)

        unified_flow.sort(key=lambda x: x.get("_epoch_timestamp", 0))

        # Find first and last events with valid timestamps
        events_with_timestamps = [e for e in unified_flow if e.get("_epoch_timestamp", 0) > 0]

        if events_with_timestamps:
            start_time = format_timestamp(events_with_timestamps[0].get("_epoch_timestamp"))
            end_time = format_timestamp(events_with_timestamps[-1].get("_epoch_timestamp"))
        else:
            start_time = "Unknown"
            end_time = "Unknown"

        all_reconstructed_conversations.append({
            "session_metadata": {
                "start_time": start_time,
                "end_time": end_time,
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
        start_time=None,  # Set to None to include all conversations
        end_time=None
    )
