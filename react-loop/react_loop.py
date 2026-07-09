from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import anthropic
import json
from datetime import date

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

# Safety net: a runaway loop needs a hard ceiling.
MAX_STEPS = 10

# --- Tools -------------------------------------------------------------------

tools = [
    {
        "name": "list_emails",
        "description": (
            "Lists the corresponding emails for the user's team. Use this tool "
            "to get attendee emails when creating calendar events. No parameters."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Creates a calendar event in the user's calendar. Takes a title, "
            "ISO start/end times, and a list of attendee emails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":     {"type": "string"},
                "start":     {"type": "string", "format": "date-time"},
                "end":       {"type": "string", "format": "date-time"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start", "end"],
        },
    },
]

def run_tool(name, tool_input):
    """Execute a tool. Returns (result, is_error) so failures flow back to the
    model as observations it can react to, instead of crashing the loop."""
    try:
        if name == "list_emails":
            return {
                "Daniel Smith":   "dan@abc.com",
                "James Jones":    "james.j@abc.com",
                "Alice Anderson": "alice@abc.com",
            }, False
        if name == "create_calendar_event":
            return {"event_id": "event_123", "status": "success"}, False
        return {"error": f"Tool {name!r} not found"}, True
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}, True

# --- The ReAct loop ----------------------------------------------------------

SYSTEM = (
    "You are a personal assistant who helps the user manage their calendar. "
    f"Today's date is {date.today().isoformat()}."
)

messages = [{
    "role": "user",
    "content": (
        "Create me a sales performance review meeting with James and Daniel "
        "next Wednesday at 1pm for 2 hours."
    ),
}]

print(f"[SYSTEM] {SYSTEM}")
print(f"[USER] {messages[0]['content']}")

step = 1
while True:
    response = client.messages.create(
        model=MODEL,
        system=SYSTEM,
        max_tokens=1024,
        tools=tools,
        thinking={"type": "adaptive"},
        messages=messages,
    )

    # A turn with no tool calls is the final answer — the healthy exit.
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    print(f"\n[STEP {step}]" if tool_calls else "\n[FINAL]")

    for block in response.content:
        if block.type == "thinking" and block.thinking:
            print(f"[THINKING] {block.thinking.strip()}")
        elif block.type == "text":
            print(f"[CLAUDE] {block.text.strip()}")

    if not tool_calls:
        break

    if step > MAX_STEPS:
        print(f"[MAX STEPS] Cut off after {MAX_STEPS} steps without a final answer.")
        break

    messages.append({"role": "assistant", "content": response.content})

    # Every tool_use needs a matching tool_result, all in ONE user message.
    tool_results = []
    for tool_use in tool_calls:
        print(f"[TOOL] {tool_use.name}({json.dumps(tool_use.input)})")
        result, is_error = run_tool(tool_use.name, tool_use.input)
        print(f"[RESULT]{' (error)' if is_error else ''} {json.dumps(result)}")
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": json.dumps(result),
            "is_error": is_error,
        })

    messages.append({"role": "user", "content": tool_results})
    step += 1
