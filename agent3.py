from langgraph.graph import MessageGraph
from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from phantom_index import load_phantoms, PhantomIndex
import os, json, operator
import sqlite3
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
import uuid

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

conn = sqlite3.connect("chat_memory.db", check_same_thread=False)
memory = SqliteSaver(conn)

PHANTOMS_PATH = 'phantoms.json'  # adjust path if needed

class PhantomAgent:
    def __init__(self, checkpointer, model_name="gpt-4.1-mini"):
        phantoms = load_phantoms(PHANTOMS_PATH)
        self.index = PhantomIndex(phantoms)
        self.phantoms = phantoms
        self.llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model=model_name, temperature=0)
        self.graph = self._build_graph()
        self.agent = self.graph.compile(checkpointer=checkpointer)
        self.phantom_lookup = {phantom["id"]: phantom for phantom in phantoms}

    # --- Extract goal from messages list ---
    def extract_goal(self, messages: list[dict]) -> str:
        for msg in reversed(messages):
            if self.get_role(msg) == "user":
                return msg.content
        return ""


    def get_role(self, msg):
        if isinstance(msg, HumanMessage):
            return "user"
        elif isinstance(msg, SystemMessage):
            return "system"
        elif isinstance(msg, AIMessage):
            return "assistant"
        else:
            return "unknown"
    # --- Nodes receive `messages` list directly ---
    def node_find_phantoms(self, messages):
        goal = self.extract_goal(messages)
        candidates=self.index.search_index(goal, k=10)
        # Format for display (optional, helpful for debugging)
        print("Candidates:", candidates)
        return AIMessage(
            content=f"Found {len(candidates)}",
            additional_kwargs={"candidates": candidates}
        )

    def node_plan_workflow(self, messages, candidates=None):
        formatted_candidates=[]
        goal = self.extract_goal(messages)
        # candidates = candidates or []
        candidates = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "candidates" in msg.additional_kwargs:
                candidates = msg.additional_kwargs["candidates"]
            break

        # If no candidates found, print warning
        if not candidates:
            print("[WARN] No candidates passed from previous node")
        else:
            prompt_text = (
                f"You are an AI planner that creates workflows for lead generation. \
                    The user has a set of available phantoms described below \
                    \n\nAvailable tools:\n{json.dumps(candidates, indent=2)}\n\n"
                "Your job: 1) Read the user’s goal carefully. Goal: {goal}\n\n  \
                2)Select the most relevant phantoms (only from the provided list). \
                3) Produce a plan: a sequence of steps where each step calls one phantom. \
                4) Make sure the plan flows logically: search → enrich → find contact → outreach. \
                5)Do NOT invent tools that are not in the provided list." \
                "Return JSON with key 'plan' that is an ordered list of phantom IDs."
            )
            prompt = [
                {"role": "system", "content": "You are an AI assistant that designs lead-generation workflows."},
                {"role": "user", "content": prompt_text}
            ]
            response = self.llm.invoke(prompt)
            print(response)
            try:
                plan_ids = json.loads(response.content)["plan"]
            except Exception:
                plan_ids = [p["id"] for p in phantom_list[:3]]

            selected = [p for p in self.phantoms if p["id"] in plan_ids]
            formatted = "\n".join(f"- {p['id']}: {p.get('description', '')}" for p in selected)

            return AIMessage(
                content=f"Here's the proposed plan:\n\n{formatted}",
                additional_kwargs={"plan": selected}
            )

    def node_user_approval(self, messages, plan=None):
        goal = self.extract_goal(messages)
        plan = plan or []
        approved = present_workflow_to_user(goal, plan)
        if not approved:
            return AIMessage(content="The workflow has is not approved. ", additional_kwargs={"approved": False, "plan": []})
        return AIMessage(content="The workflow has is approved. ", additional_kwargs={"approved": True, "plan": plan})

    def node_prepare_inputs(self, messages, user_inputs=None):
        goal = self.extract_goal(messages)
        plan = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "plan" in msg.additional_kwargs:
                plan = msg.additional_kwargs["plan"]

        if not plan:
            return AIMessage(content="No plan found to prepare inputs for.", additional_kwargs={"phantom_inputs": []})

        # Instead of input(), expect user_inputs dict keyed by phantom_id
        phantom_inputs = []
        if user_inputs is None:
            user_inputs = {}

        for phantom in plan:
            pid = phantom["id"]
            input_value = user_inputs.get(pid, "")
            phantom_inputs.append({
                "phantom_id": pid,
                "input": {
                    "goal": goal,
                    "user_input": input_value
                }
            })

        return AIMessage(
            content="User inputs collected.",
            additional_kwargs={"phantom_inputs": phantom_inputs}
        )

    def node_execute(self, messages):
        goal = self.extract_goal(messages)

        phantom_inputs = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "phantom_inputs" in msg.additional_kwargs:
                phantom_inputs = msg.additional_kwargs["phantom_inputs"]
                break
        logs = []
        for i, phantom_input in enumerate(phantom_inputs, 1):
            phantom_id = phantom_input["phantom_id"]
            input_data = phantom_input["input"]

            print(f"\n[{i}/{len(phantom_inputs)}] Running phantom: {phantom_id}")
            produced = {
                "result": f"Simulated result for {phantom_id} with input {input_data}"
            }

            log_entry = {
                "phantom_id": phantom_id,
                "status": "simulated_ok",
                "produced": produced,
                "timestamp_iso": "2025-09-19T12:00:00Z",
            }
            logs.append(log_entry)
            print(f"✅ Output: {produced}")
        return AIMessage(
        content="Phantom execution completed.",
        additional_kwargs={"logs": logs}
    )

    def node_logger(self, messages):
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "logs" in msg.additional_kwargs:
                logs = msg.additional_kwargs["logs"]
        print("\nFinal logs:", logs)
        return AIMessage(content=f"The process is complete", additional_kwargs={"done": True})

    # --- Graph construction ---
    def _build_graph(self):
        graph = MessageGraph()
        graph.add_node("find_phantoms", self.node_find_phantoms)
        graph.add_node("plan_workflow", self.node_plan_workflow)
        graph.add_node("user_approval", self.node_user_approval)
        graph.add_node("prepare_inputs", self.node_prepare_inputs)
        graph.add_node("execute", self.node_execute)
        graph.add_node("logger", self.node_logger)

        graph.add_edge("find_phantoms", "plan_workflow")
        graph.add_edge("plan_workflow", "user_approval")
        graph.add_edge("user_approval", "prepare_inputs")
        graph.add_edge("prepare_inputs", "execute")
        graph.add_edge("execute", "logger")

        graph.set_entry_point("find_phantoms")
        graph.set_finish_point("logger")

        return graph

    # --- Runner ---
    def run(self, messages):
        return self.agent.invoke(
            messages,
            config={"configurable": {"thread_id": str(uuid.uuid4())}}
        )


if __name__ == "__main__":
    print("Welcome to the LangGraph PhantomBuster Agent (GPT-based).")
    user_input = input("Enter your lead generation goal: ")
    agent = PhantomAgent(checkpointer=memory)

    initial_messages = [{"role": "user", "content": user_input}]
    result = agent.run(initial_messages)
    print("\nAgent finished. Result:", result)
