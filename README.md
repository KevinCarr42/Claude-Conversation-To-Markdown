# Claude to Markdown

A Python utility that converts Claude Code agent conversations from raw JSONL transcripts into structured, human-readable Markdown documentation.

## Why

Claude Code stores conversation history as `.jsonl` files spread across project and subagent directories. These raw logs are difficult to read and nearly impossible to use for reference. This tool reconstructs the full conversation timeline — including interleaved subagent threads — and exports it as clean Markdown with speaker labels, timestamps, and proper formatting.

This is especially useful for preserving multi-agent workflows such as structured debates, architecture decision records (ADRs), and collaborative problem-solving sessions.

## Features

- **JSONL Parsing** — Reads Claude Code's native `.jsonl` conversation logs
- **Subagent Reconstruction** — Merges main thread and subagent threads into a single unified timeline using timestamp correlation
- **Agent Identification** — Detects agent names from system prompts and `Task` tool invocations (e.g., `@debate`, `@statler`, `@waldorf`, `@debate-judge`)
- **Thinking Block Preservation** — Retains `<thinking>` blocks in the output for full transparency
- **Time Filtering** — Optionally filter conversations by start and end time
- **Dual Export** — Outputs both a structured JSON intermediate file and a final Markdown document

## Output Format

The generated Markdown includes:

- Session metadata (start/end time, event count)
- Speaker headers (`## USER`, `## ASSISTANT`, `## USER [@agent-name]`)
- Timestamps for each message
- Grouped consecutive messages from the same speaker
- Horizontal rule separators between speakers

## Usage

1. Place your Claude Code conversation `.jsonl` files in `entire_conversation/projects_folder/`.

2. Run the script:

```bash
python claude_to_markdown.py
```

3. Find the output in the `output/` directory:
   - `conversation_export.json` — Structured intermediate representation
   - `conversation_export.md` — Human-readable Markdown document

### Time Filtering

To export only a specific time range, modify the `export_merged_log` call in `__main__`:

```python
export_merged_log(
    claude_code_conversation_path,
    json_output_file,
    start_time="2026-02-03 11:00",
    end_time="2026-02-03 12:00"
)
```

Accepted formats: `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`.

## Example

The included example captures a multi-agent debate session where:

1. A **debate agent** frames technical questions from a project's `todo.md`
2. **Statler** (lean/functional advocate) and **Waldorf** (enterprise architect) deliver opening arguments, rebuttals, and closing statements
3. An announcer provides running commentary between rounds
4. A **debate-judge agent** reviews the full transcript and issues a formal Architecture Decision Record (ADR)

The resulting Markdown serves as a permanent, readable record of the architectural decision-making process.

## Project Structure

```
ClaudeToMarkdown/
├── claude_to_markdown.py        # Main conversion script
├── entire_conversation/         # Input: raw Claude Code JSONL logs
│   └── projects_folder/         #   Project conversation files
├── output/                      # Output: generated exports
│   ├── conversation_export.json #   Structured JSON
│   └── conversation_export.md   #   Readable Markdown
└── README.md
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## License

This project is provided as-is for personal and team use.
