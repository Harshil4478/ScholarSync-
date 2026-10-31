"""AI Relief Agent page: plan, review reasoning, approve or reject, chat."""
import pandas as pd
import streamlit as st

from agent_core import (
    STOCK_LABELS, approve_proposal, get_proposals, plan_all_emergencies, reject_proposal,
)
from llm_agent import llm_available, run_agent

SUPPLY_KEYS = ("water_litres", "food_packets", "medical_kits")


def _sent_text(quantities):
    parts = [f"{STOCK_LABELS[k]} {int(quantities[k])}" for k in SUPPLY_KEYS if quantities.get(k)]
    return " · ".join(parts) or "nothing"


def render_ai_agent():
    st.header("🤖 AI Relief Coordination Agent")
    st.caption("The agent analyses emergencies, stock and road routes, then PROPOSES dispatches. "
               "Nothing is sent until you press Approve.")

    _flash()
    pending = get_proposals("Pending")
    _render_pending(pending)

    plan_tab, chat_tab, history_tab = st.tabs(["📋 Plan all emergencies", "💬 Ask the agent", "🗂 Decision history"])
    with plan_tab:
        _render_plan_tab()
    with chat_tab:
        _render_chat_tab()
    with history_tab:
        _render_history()


def _render_pending(pending):
    st.subheader(f"⏳ Waiting for your decision ({len(pending)})")
    if not pending:
        st.info("No pending proposals. Run 'Plan all emergencies' or ask the agent.")
        return
    for proposal in pending:
        source = "AI assistant" if proposal["source"] == "ai" else "Planner"
        title = f"Proposal #{proposal['id']} · {proposal['emergency_label']} → {proposal['centre_name']}"
        with st.expander(title, expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("Road distance", f"{proposal['distance_km']:.1f} km")
            c2.metric("Drive time", f"{proposal['duration_min']:.0f} min")
            c3.metric("Need covered", f"{(proposal['coverage'] or 0) * 100:.0f}%")
            st.write("**Would send:** " + _sent_text(proposal))
            st.text(proposal["reasoning"] or "")
            st.caption(f"Source: {source} · created {proposal['created_at']}")
            approve_col, reject_col, _ = st.columns([1, 1, 2])
            if approve_col.button("✅ Approve dispatch", key=f"agent_approve_{proposal['id']}", type="primary"):
                try:
                    dispatch_id, sent, note = approve_proposal(proposal["id"])
                    st.session_state.agent_flash = (
                        "success", f"Dispatch #{dispatch_id} approved: {_sent_text(sent)}. {note}".strip())
                except ValueError as error:
                    st.session_state.agent_flash = ("error", str(error))
                st.rerun()
            if reject_col.button("✖ Reject", key=f"agent_reject_{proposal['id']}"):
                reject_proposal(proposal["id"])
                st.session_state.agent_flash = ("info", f"Proposal #{proposal['id']} rejected.")
                st.rerun()


def _flash():
    kind, message = st.session_state.pop("agent_flash", (None, None))
    if kind:
        getattr(st, kind)(message)


def _render_plan_tab():
    st.write("The planner goes through active emergencies from most to least urgent. Each proposal reserves stock, "
             "so two emergencies are never planned against the same supplies.")
    if st.button("🧭 Plan all emergencies", type="primary", key="agent_plan_all"):
        with st.spinner("Checking stock and calculating road routes..."):
            proposals, unserved = plan_all_emergencies()
        st.session_state.agent_last_run = (len(proposals), [
            f"{_u[0]['location']} (#{_u[0]['id']}): {_u[1]}" for _u in unserved])
        st.rerun()
    last = st.session_state.get("agent_last_run")
    if last:
        count, unserved = last
        st.success(f"Last run created {count} proposal(s).")
        for line in unserved:
            st.warning("Not planned: " + line)


def _render_chat_tab():
    ok, why = llm_available()
    if not ok:
        st.info(f"{why}\n\nThe 'Plan all emergencies' tab works without it.")
        return
    st.session_state.setdefault("agent_chat", [])
    for role, text in st.session_state.agent_chat:
        with st.chat_message(role):
            st.write(text)
    with st.form("agent_chat_form", clear_on_submit=True):
        question = st.text_area("Ask the agent", placeholder="e.g. Which emergency is most at risk of running out of supplies?")
        sent = st.form_submit_button("Send", type="primary")
    if sent and question.strip():
        history = [{"role": role, "content": text} for role, text in st.session_state.agent_chat]
        try:
            with st.spinner("The agent is checking the data..."):
                answer, created = run_agent(question.strip(), history=history)
        except Exception as error:  # network, auth, quota, model name...
            st.error(f"The assistant could not answer: {error}")
            return
        st.session_state.agent_chat.append(("user", question.strip()))
        st.session_state.agent_chat.append(("assistant", answer))
        if created:
            st.session_state.agent_flash = ("info", f"The agent created proposal(s) {', '.join('#' + str(i) for i in created)} "
                                                    "above. Review them before approving.")
        st.rerun()
    if st.session_state.agent_chat and st.button("Clear conversation", key="agent_clear"):
        st.session_state.agent_chat = []
        st.rerun()


def _render_history():
    decided = [p for p in get_proposals() if p["status"] != "Pending"]
    if not decided:
        st.info("No decisions yet.")
        return
    frame = pd.DataFrame(decided)[["id", "emergency_label", "centre_name", "water_litres", "food_packets",
                                   "medical_kits", "status", "source", "dispatch_id", "created_at", "decided_at"]]
    st.dataframe(frame, hide_index=True, use_container_width=True)
