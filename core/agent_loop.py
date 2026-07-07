"""
core/agent_loop.py

Shared ReAct loop used by both pipeline_agent and chat_agent.
Each agent passes its own system prompt, tool definitions, and dispatcher.
"""

import json
import anthropic
from typing import Callable

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_ITERATIONS = 20  # safety ceiling — prevents infinite loops


def load_memory(paths: list[str]) -> str:
    """
    Load one or more .md memory files and concatenate them
    into a single string for injection into the system prompt.
    """
    sections = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                sections.append(f"<!-- {path} -->\n{content}")
        except FileNotFoundError:
            pass  # memory file doesn't exist yet, skip silently
    return "\n\n".join(sections)


def build_system_prompt(base_prompt: str, memory_paths: list[str]) -> str:
    """
    Combine the agent's base system prompt with injected memory files.
    Memory is appended as a clearly labelled section.
    """
    memory = load_memory(memory_paths)
    if not memory:
        return base_prompt
    return f"{base_prompt}\n\n---\n## Agent Memory\n{memory}"


def run_agent_loop(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    dispatch: Callable[[str, dict], any],
    on_text: Callable[[str], None] | None = None,
) -> str:
    """
    Core ReAct loop. Runs until Claude stops calling tools or max iterations hit.

    Args:
        messages:      Conversation history. Mutated in-place as the loop runs.
        system_prompt: Full system prompt (base + injected memory).
        tools:         List of tool definitions in Anthropic JSON schema format.
        dispatch:      Function(tool_name, tool_input) → result. Agent-specific.
        on_text:       Optional callback called with each text chunk Claude emits.

    Returns:
        Claude's final text response.
    """
    client = anthropic.Anthropic()
    final_text = ""

    for _ in range(MAX_ITERATIONS):

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        tool_uses = []
        text_blocks = []

        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)
                if on_text:
                    on_text(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_blocks:
            final_text = "\n".join(text_blocks)

        messages.append({
            "role": "assistant",
            "content": response.content,
        })

        if response.stop_reason == "end_turn" or not tool_uses:
            break

        tool_results = []
        for tool_use in tool_uses:
            print(f"  [tool] {tool_use.name}({json.dumps(tool_use.input)})")

            try:
                result = dispatch(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })
            except Exception as e:
                # Return the error to Claude so it can reason about failures
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps({"error": str(e)}),
                    "is_error": True,
                })

        messages.append({
            "role": "user",
            "content": tool_results,
        })

    else:
        print(f"[warn] Agent hit MAX_ITERATIONS ({MAX_ITERATIONS}). Stopping.")

    return final_text
