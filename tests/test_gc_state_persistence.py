"""gc_state must be a real field on AgentState and survive save/reload.

Guard against the leak class where ContextGC-trashed tool_call_ids silently
re-materialize after /save + /load because they were only held in a per-turn
config dict, not on AgentState itself.
"""
from __future__ import annotations

import json

from agent import AgentState
from context_gc import GCState
from commands.session import _build_session_data, _restore_state_from_data


def test_agent_state_has_gc_state_by_default():
    state = AgentState()
    assert isinstance(state.gc_state, GCState)
    assert state.gc_state.trashed_ids == set()
    assert state.gc_state.notes == {}


def test_two_agent_states_have_independent_gc_state():
    a = AgentState()
    b = AgentState()
    a.gc_state.trashed_ids.add("toolcall_1")
    assert "toolcall_1" not in b.gc_state.trashed_ids


def test_session_save_includes_gc_state_as_sortable_json():
    state = AgentState()
    state.gc_state.trashed_ids = {"id_b", "id_a", "id_c"}
    state.gc_state.notes = {"task": "do the thing"}

    data = _build_session_data(state)
    serialized = json.dumps(data)
    assert "gc_state" in data
    assert data["gc_state"]["trashed_ids"] == ["id_a", "id_b", "id_c"]
    assert data["gc_state"]["notes"] == {"task": "do the thing"}
    assert '"trashed_ids":' in serialized


def test_session_load_restores_gc_state():
    fresh = AgentState()
    _restore_state_from_data(fresh, {
        "messages": [],
        "gc_state": {
            "trashed_ids": ["a", "b"],
            "notes": {"k": "v"},
            "snippets": {},
        },
    })
    assert fresh.gc_state.trashed_ids == {"a", "b"}
    assert fresh.gc_state.notes == {"k": "v"}


def test_session_load_missing_gc_state_returns_fresh_empty():
    fresh = AgentState()
    _restore_state_from_data(fresh, {"messages": []})
    assert fresh.gc_state.trashed_ids == set()
    assert fresh.gc_state.notes == {}


def test_save_then_load_roundtrip_preserves_trashed_ids():
    """End-to-end: trash ids, serialize, rehydrate — ids must still be trashed.

    This is the exact leak the bug class introduces: if roundtrip drops
    trashed_ids, previously-elided tool_results come back into context and
    inflate the prompt by whatever they were trimmed from.
    """
    before = AgentState()
    before.gc_state.trashed_ids = {"tool_a", "tool_b"}
    before.gc_state.snippets = {"tool_c": {"keep_after": "### Result"}}

    data = json.loads(json.dumps(_build_session_data(before), default=str))
    after = AgentState()
    _restore_state_from_data(after, data)

    assert after.gc_state.trashed_ids == {"tool_a", "tool_b"}
    assert after.gc_state.snippets == {"tool_c": {"keep_after": "### Result"}}
