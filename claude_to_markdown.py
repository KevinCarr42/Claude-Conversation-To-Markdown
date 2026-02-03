import json
from pathlib import Path
from datetime import datetime


def load_jsonl_events(file_path):
    events = []
    fname = Path(file_path).name
    with open(file_path, 'r', encoding='utf-8') as file_handle:
        content = file_handle.read().strip()
    
    if not content:
        return events
    
    decoder = json.JSONDecoder()
    idx = 0
    
    while idx < len(content):
        while idx < len(content) and content[idx].isspace():
            idx += 1
        
        if idx >= len(content):
            break
        
        try:
            obj, end_idx = decoder.raw_decode(content, idx)
            obj['_source_file'] = fname
            events.append(obj)
            idx = end_idx
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping malformed JSON in {file_path} at position {idx} - {e}")
            break
    
    return events


def format_timestamp(epoch_time):
    return datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')


def parse_iso_timestamp(iso_str):
    if not iso_str:
        return 0
    try:
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


def extract_text_content(content_item):
    if isinstance(content_item, str):
        return content_item
    if isinstance(content_item, dict):
        if content_item.get('type') == 'text':
            return content_item.get('text', '')
        if content_item.get('type') == 'thinking':
            return f"<thinking>\n{content_item.get('thinking', '')}\n</thinking>"
    return ''


def extract_message_text(message_data):
    if not message_data:
        return ''
    
    content = message_data.get('content', '')
    
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_parts = []
        for item in content:
            extracted = extract_text_content(item)
            if extracted:
                text_parts.append(extracted)
        return '\n\n'.join(text_parts)
    
    return ''


def extract_agent_name_from_events(events_list):
    agent_names = {}
    agent_type_by_timestamp = {}
    
    for event in events_list:
        if event.get('type') == 'assistant' and not event.get('agentId'):
            message_data = event.get('message', {})
            content = message_data.get('content', [])
            
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        if item.get('name') == 'Task':
                            tool_input = item.get('input', {})
                            subagent_type = tool_input.get('subagent_type', '')
                            if subagent_type:
                                event_timestamp = event.get('_epoch_timestamp', 0)
                                agent_type_by_timestamp[event_timestamp] = subagent_type
    
    for event in events_list:
        agent_id = event.get('agentId')
        if not agent_id or agent_id in agent_names:
            continue
        
        if event.get('type') == 'user':
            message_data = event.get('message', {})
            content = message_data.get('content', '')
            
            if isinstance(content, str) and 'You are' in content:
                lines = content.split('\n')
                first_line = lines[0]
                
                if first_line.startswith('You are '):
                    agent_name = first_line.replace('You are ', '').split(',')[0].split('.')[0].strip()
                    agent_names[agent_id] = agent_name
            else:
                event_timestamp = event.get('_epoch_timestamp', 0)
                closest_task_timestamp = min(
                    agent_type_by_timestamp.keys(),
                    key=lambda ts: abs(ts - event_timestamp),
                    default=None
                )
                if closest_task_timestamp and abs(closest_task_timestamp - event_timestamp) < 5:
                    agent_names[agent_id] = agent_type_by_timestamp[closest_task_timestamp]
    
    return agent_names


def format_agent_label(event_data, agent_name_map):
    agent_id = event_data.get('agentId')
    
    if agent_id:
        agent_name = agent_name_map.get(agent_id)
        if agent_name:
            return f"@{agent_name}"
        return f"Agent-{agent_id}"
    
    return None


def json_to_markdown(json_data, output_directory, min_conversation_length=20):
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    markdown_files = []
    
    for session_index, session in enumerate(json_data):
        markdown_lines = []
        session_metadata = session.get('session_metadata', {})
        session_events = session.get('events', [])
        
        if len(session_events) < min_conversation_length:
            continue
        
        agent_name_map = extract_agent_name_from_events(session_events)
        
        markdown_lines.append(f"# Conversation\n")
        markdown_lines.append(f"**Main File:** {session_metadata.get('source_file', 'Unknown')}")
        markdown_lines.append(f"\n**Start:** {session_metadata.get('start_time', 'Unknown')}")
        markdown_lines.append(f"**End:** {session_metadata.get('end_time', 'Unknown')}")
        markdown_lines.append(f"**Total Events:** {session_metadata.get('event_count', 0)}\n")
        markdown_lines.append("---\n")
        
        previous_speaker_key = None
        grouped_messages = []
        
        for event in session_events:
            event_type = event.get('type')
            timestamp_str = event.get('timestamp', '')
            source_file = event.get('_source_file', 'Unknown')
            
            if event_type in ['user', 'assistant']:
                agent_label = format_agent_label(event, agent_name_map)
                message_data = event.get('message', {})
                message_role = message_data.get('role', event_type)
                message_text = extract_message_text(message_data)
                
                if not message_text:
                    continue
                
                current_speaker_key = (message_role, agent_label, source_file)
                
                if timestamp_str:
                    timestamp_formatted = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp_formatted = None
                
                if current_speaker_key != previous_speaker_key:
                    if grouped_messages:
                        markdown_lines.extend(grouped_messages)
                        markdown_lines.append("---\n")
                        grouped_messages = []
                    
                    header = f"## {message_role.upper()}"
                    if agent_label:
                        header += f" [{agent_label}]"
                    
                    markdown_lines.append(f"{header}\n")
                    if source_file != session_metadata.get('source_file'):
                        markdown_lines.append(f"**Subagent File:** {source_file}\n")
                    previous_speaker_key = current_speaker_key
                
                if timestamp_formatted:
                    grouped_messages.append(f"`{timestamp_formatted}`")
                grouped_messages.append(f"{message_text}\n")
        
        if grouped_messages:
            markdown_lines.extend(grouped_messages)
            markdown_lines.append("---\n")
        
        start_time_str = session_metadata.get('start_time', 'Unknown')
        if start_time_str != 'Unknown':
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
            timestamp_string = start_dt.strftime('%Y%m%d_%H%M')
        else:
            timestamp_string = f"unknown_{session_index + 1:03d}"
        
        session_filename = f"session_{timestamp_string}.md"
        session_filepath = output_dir / session_filename
        
        with open(session_filepath, 'w', encoding='utf-8') as markdown_file:
            markdown_file.write('\n'.join(markdown_lines))
        
        markdown_files.append(session_filepath)
    
    return markdown_files


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
        
        is_subagent = ('subagents' in str(file_path) or
                       any('agentId' in event for event in thread_events))
        
        if is_subagent:
            subagent_threads.append(thread_events)
        else:
            main_thread_files.append((file_path, thread_events))
    
    all_reconstructed_conversations = []
    consumed_subagent_indices = set()
    
    for file_path, main_events in main_thread_files:
        for event in main_events:
            event['_epoch_timestamp'] = parse_iso_timestamp(event.get("timestamp"))
        
        main_events.sort(key=lambda x: x.get("_epoch_timestamp", 0))
        
        session_start = main_events[0].get("_epoch_timestamp", 0)
        session_end = main_events[-1].get("_epoch_timestamp", 0)
        
        if start_ts and session_end < start_ts:
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
                "event_count": len(unified_flow),
                "source_file": Path(file_path).name
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
    json_output_filename = "conversation_export.json"
    claude_code_conversation_path = Path("all_conversations")
    start_time = "2026-01-30"
    end_time = "2026-02-03"
    
    output_directory.mkdir(parents=True, exist_ok=True)
    json_output_file = output_directory / json_output_filename
    
    export_merged_log(
        claude_code_conversation_path,
        json_output_file,
        start_time=start_time,
        end_time=end_time
    )
    
    with open(json_output_file, 'r', encoding='utf-8') as json_file:
        conversation_data = json.load(json_file)
    
    markdown_files = json_to_markdown(conversation_data, output_directory, min_conversation_length=20)
    
    print(f"Exported JSON to: {json_output_file}")
    print(f"Exported {len(markdown_files)} Markdown files to: {output_directory}")
    for md_file in markdown_files:
        print(f"  - {md_file.name}")
