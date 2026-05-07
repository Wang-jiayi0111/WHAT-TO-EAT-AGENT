"""T-012 / FR-18 / 4.5: L4 snapshot, run_memory_keeper_safe, schedule after reply."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.nodes.memory_keeper import (
    build_memory_keeper_snapshot,
    messages_from_keeper_snapshot,
    run_memory_keeper_safe,
    schedule_memory_keeper_after_reply,
    serialize_messages_for_keeper,
)


def test_serialize_messages_for_keeper_human_ai_only():
    msgs = [
        HumanMessage("hello"),
        AIMessage("hi"),
        HumanMessage("bye"),
    ]
    rows = serialize_messages_for_keeper(msgs)
    assert rows == [
        {"role": "human", "content": "hello"},
        {"role": "ai", "content": "hi"},
        {"role": "human", "content": "bye"},
    ]


def test_messages_roundtrip_snapshot():
    msgs = [HumanMessage("a"), AIMessage("b")]
    snap = serialize_messages_for_keeper(msgs)
    back = messages_from_keeper_snapshot(snap)
    assert len(back) == 2
    assert back[0].content == "a"
    assert back[1].content == "b"


def test_build_memory_keeper_snapshot_immutable_shape():
    snap = build_memory_keeper_snapshot("house_A", [HumanMessage("x")])
    assert snap["scope_id"] == "house_A"
    assert snap["messages"] == [{"role": "human", "content": "x"}]


@pytest.mark.asyncio
async def test_run_memory_keeper_safe_swallows_persist_error():
    with patch(
        "src.agent.nodes.memory_keeper.run_memory_keeper_persist",
        new_callable=AsyncMock,
        side_effect=RuntimeError("persist failed"),
    ):
        await run_memory_keeper_safe(
            {
                "scope_id": "u1",
                "messages": [{"role": "human", "content": "test"}],
            }
        )


@pytest.mark.asyncio
async def test_schedule_memory_keeper_after_reply_runs_safe():
    with patch(
        "src.agent.nodes.memory_keeper.run_memory_keeper_safe",
        new_callable=AsyncMock,
    ) as safe:
        schedule_memory_keeper_after_reply(
            "scope_z",
            [HumanMessage("ping"), AIMessage("pong")],
        )
        for _ in range(50):
            await asyncio.sleep(0.01)
            if safe.await_count >= 1:
                break
        assert safe.await_count >= 1
        arg = safe.await_args[0][0]
        assert arg["scope_id"] == "scope_z"
        assert len(arg["messages"]) == 2


def test_schedule_memory_keeper_without_running_loop_no_raise():
    """Sync context without asyncio loop: skip quietly (DEV-014)."""

    def sync_caller():
        schedule_memory_keeper_after_reply("solo", [HumanMessage("only")])

    sync_caller()
