from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import anthropic
import asyncio
import json
import time
from datetime import date, timedelta

client = anthropic.AsyncAnthropic()
MODEL = "claude-sonnet-4-6"

# Safety net: a runaway loop needs a hard ceiling.
MAX_STEPS = 10

# Simulated network latency per tool call, so the trace can show that N
# parallel calls take about as long as one, not N times as long.
TOOL_LATENCY = 1.0

# --- Tools -------------------------------------------------------------------

tools = [
    {
        "name": "list_emails",
        "description": (
            "Lists the emails of everyone in the team. Use this to look up an "
            "email before checking a calendar or creating an event. No parameters."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_calendar",
        "description": (
            "Checks the calendar of a specific person by email. You MUST call "
            "this for every attendee before creating a calendar event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Creates a calendar event. Takes a title, ISO start/end times, and "
            "an optional list of attendee emails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":     {"type": "string"},
                "start":     {"type": "string", "format": "date-time"},
                "end":       {"type": "string", "format": "date-time"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"},
                },
            },
            "required": ["title", "start", "end"],
        },
    },
]

# --- Mock infra ----------------------------------------------------------------

TODAY = date.today()
NEXT_WED = TODAY + timedelta(days=(2 - TODAY.weekday()) % 7 or 7)

def iso(day, hour, minute=0):
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00Z"

EMAILS = {
    "James Jones":  "james@abc.com",
    "Sarah Smith":  "sarah@abc.com",
    "Trish Taylor": "trish@abc.com",
}

CALENDAR = {
    "james@abc.com": [
        {"title": "Monthly Review",      "start": iso(NEXT_WED - timedelta(days=2), 10), "end": iso(NEXT_WED - timedelta(days=2), 11)},
        {"title": "1-on-1 with Manager", "start": iso(NEXT_WED + timedelta(days=1), 9),  "end": iso(NEXT_WED + timedelta(days=1), 9, 45)},
    ],
    "sarah@abc.com": [
        {"title": "Marketing Brainstorm", "start": iso(NEXT_WED, 10, 30), "end": iso(NEXT_WED, 12)},
        {"title": "Client Onboarding",    "start": iso(NEXT_WED + timedelta(days=2), 13), "end": iso(NEXT_WED + timedelta(days=2), 14)},
    ],
    "trish@abc.com": [
        {"title": "Sprint Planning", "start": iso(NEXT_WED + timedelta(days=2), 11), "end": iso(NEXT_WED + timedelta(days=2), 13)},
    ],
}

async def run_tool(name, tool_input):
    """Execute a tool. Returns (result, is_error) so failures flow back to the
    model as observations it can react to, instead of crashing the loop."""
    await asyncio.sleep(TOOL_LATENCY)  # stand-in for a real network call
    try:
        if name == "list_emails":
            return EMAILS, False
        if name == "check_calendar":
            return CALENDAR.get(tool_input["email"], []), False
        if name == "create_calendar_event":
            return {"event_id": "evnt_123", "status": "success"}, False
        return {"error": f"Tool {name!r} not found"}, True
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}, True

async def execute_tool(tool_use):
    """Run one tool call and wrap it as a tool_result block."""
    result, is_error = await run_tool(tool_use.name, tool_use.input)
    print(f"[RESULT]{' (error)' if is_error else ''} {tool_use.name} → {json.dumps(result)}")
    return {
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": json.dumps(result),
        "is_error": is_error,
    }

# --- Agent loop ----------------------------------------------------------------
SYSTEM = (
    "You are a personal assistant who manages the user's calendar. "
    f"Today's date is {TODAY.isoformat()}."
)

async def main():
    messages = [{
        "role": "user",
        "content": (
            "Create me a meeting event with James and Sarah please for next "
            "Wednesday at 2pm for 1 hour."
        ),
    }]

    print(f"[SYSTEM] {SYSTEM}")
    print(f"[USER] {messages[0]['content']}")

    step = 1
    while True:
        response = await client.messages.create(
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

        for tool_use in tool_calls:
            print(f"[TOOL] {tool_use.name}({json.dumps(tool_use.input)})")

        # Run every tool call in this turn CONCURRENTLY. gather() preserves
        # order, so each tool_result lines up with its tool_use - and all
        # results still go back in ONE user message.
        started = time.perf_counter()
        tool_results = await asyncio.gather(*(execute_tool(tu) for tu in tool_calls))
        print(f"[ELAPSED] {len(tool_calls)} tool call(s) in {time.perf_counter() - started:.2f}s")

        messages.append({"role": "user", "content": list(tool_results)})
        step += 1

asyncio.run(main())
