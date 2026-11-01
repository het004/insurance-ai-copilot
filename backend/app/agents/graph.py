"""LangGraph ReAct-style agent.

    START ──► agent (Gemini 2.5 Flash + bound tools)
                │  tool_calls?           ┌────────────┐
                ├──── yes ─────────────► │   tools    │ (ToolNode executes 1..n tools)
                │                        └─────┬──────┘
                │ ◄────────────────────────────┘ (results appended as ToolMessages)
                └──── no ──► END  (final natural-language answer)

Conversation memory: a checkpointer keyed by thread_id (= chat session_id) persists the
full message history, so follow-up turns ("yes, renew it") keep their context.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.prompts import build_system_prompt
from app.services import gemini_service
from app.services.insurance_service import get_customer
from app.services.session_store import session_store
from app.tools import ALL_TOOLS

MAX_HISTORY = 40  # messages sent to the model per turn (state keeps everything)


def _trim(messages: list[Any]) -> list[Any]:
    """Keep the recent window without orphaning ToolMessages from their AI tool call."""
    if len(messages) <= MAX_HISTORY:
        return messages
    window = messages[-MAX_HISTORY:]
    while window and window[0].type == "tool":
        window = window[1:]
    return window


def build_graph():
    llm = gemini_service.get_chat_model().bind_tools(ALL_TOOLS)

    def agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
        # Identity is re-read every step: a tool in this very turn may have just verified the customer.
        sess = session_store.get((config.get("configurable") or {}).get("thread_id"))
        customer = None
        if sess.customer_id:
            try:
                customer = get_customer(sess.customer_id)
            except Exception:  # noqa: BLE001
                customer = None
        msgs = [SystemMessage(build_system_prompt(sess, customer))] + _trim(state["messages"])
        return {"messages": [llm.invoke(msgs, config)]}

    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(ALL_TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    # MemorySaver = in-process memory for the POC. Swap for SqliteSaver / PostgresSaver in production.
    return g.compile(checkpointer=MemorySaver())


MERMAID = """graph TD
  START([User turn]) --> agent[Gemini 2.5 Flash<br/>+ bound tools]
  agent -->|tool_calls| tools[ToolNode<br/>generate_quote · get_customer_profile · get_policy_details<br/>create_claim · track_claim · renew_policy · knowledge_search]
  tools --> agent
  agent -->|final answer| END([Reply + cards + citations])"""
