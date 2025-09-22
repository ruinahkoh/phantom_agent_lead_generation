import streamlit as st
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from agent import PhantomAgent 

st.title("PhantomBuster Lead Gen Agent")

# --- Setup ---
conn = sqlite3.connect("chat_memory.db", check_same_thread=False)
memory = SqliteSaver(conn)
agent = PhantomAgent(checkpointer=memory)

# Initialize session stage
if "stage" not in st.session_state:
    st.session_state["stage"] = "plan"
if "plan" not in st.session_state:
    st.session_state["plan"] = []

# --- Step 1: Goal ---
goal = st.text_input("Enter your lead generation goal", value=st.session_state.get("goal", ""))

if goal:
    st.session_state["goal"] = goal

    if st.session_state["stage"] == "plan":
        # Generate or re-use plan
        if st.button("Generate Plan"):
            initial_messages = [{"role": "user", "content": goal}]
            with st.spinner("Generating workflow plan..."):
                plan_msg = agent.node_plan_workflow(initial_messages)
            plan = plan_msg.additional_kwargs.get("plan", [])
            st.session_state["plan"] = plan
            st.session_state["plan_msg"] = plan_msg

        # Display plan if exists
        if st.session_state["plan"]:
            st.write("Proposed workflow plan:")
            for p in st.session_state["plan"]:
                st.write(f"- {p['id']}: {p.get('description', '')}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve Plan ✅"):
                    st.session_state["stage"] = "inputs"
            with col2:
                if st.button("Regenerate Plan 🔄"):
                    # Just clear plan and stay in "plan" stage
                    st.session_state["plan"] = []
                    st.rerun()
    
    # Enter inputs for phantoms
    elif st.session_state["stage"] == "inputs":
        st.write("Enter inputs for each phantom:")
        user_inputs = {}
        all_inputs_filled = True

        for phantom in st.session_state["plan"]:
            input_required = agent.phantom_lookup.get(
                phantom['id'], {}
            ).get('inputs', "No input info available")

            st.markdown(f"**Input required for {phantom['id']}:** {input_required}")
            user_input = st.text_input(f"Enter input for {phantom['id']}", key=f"input_{phantom['id']}")
            user_inputs[phantom['id']] = user_input
            if not user_input.strip():
                all_inputs_filled = False

        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Back to Planning"):
                st.session_state["stage"] = "plan"
                st.rerun()
        with col2:
            if all_inputs_filled and st.button("Submit & Run Phantoms ▶️"):
                st.session_state["ready_to_execute"] = True

        # Execution
        if st.session_state.get("ready_to_execute"):
            prepare_msg = agent.node_prepare_inputs(
                messages=[st.session_state["plan_msg"]], 
                user_inputs=user_inputs
            )
            exec_msg = agent.node_execute([prepare_msg])
            logs = exec_msg.additional_kwargs.get("logs", [])

            st.subheader("Execution Logs")
            for log in logs:
                st.json(log)

            logger_msg = agent.node_logger([exec_msg])
            st.write(logger_msg.content)

            st.session_state["stage"] = "plan"   # Optionally reset to plan after execution
            st.session_state["ready_to_execute"] = False
