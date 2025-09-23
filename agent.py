from langgraph.graph import MessageGraph
from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from phantom_index import load_phantoms, PhantomIndex
from langchain.agents import Tool, ZeroShotAgent , create_react_agent, AgentExecutor
from langchain.chains.llm import LLMChain
from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
import os, json, operator
import sqlite3
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
import uuid
from langchain_core.runnables.graph_ascii import draw_ascii

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
        # dot = self.agent.get_graph()
        # print(dot.draw_mermaid() )
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

    def node_plan_workflow(self, messages):
        formatted_candidates=[]
        goal = self.extract_goal(messages)
        plan = []
       
        def search_phantoms(query: str) -> str:
            """Search available phantoms by description/tags."""
            results = self.index.search_index(query, k=5)
            return "\n".join([f"{p['id']}: {p.get('description','')}" for p in results])


        def add_to_plan(input_str: str) -> str:
            """Add a phantom to the workflow plan with rationale."""
            try:
                phantom_id, rationale = input_str.split("|", 1)
                phantom_id = phantom_id.strip()
                rationale = rationale.strip()
            except ValueError:
                return "Error: Please provide input in the format 'phantom_id | rationale'"

           

            if any(step["id"] == phantom_id for step in plan):
                return f"Phantom {phantom_id} is already in the plan. Skipping duplicate."

            ph = next((p for p in self.phantoms if p["id"] == phantom_id), None)
            if not ph:
                return f"Phantom {phantom_id} not found."
            
            plan.append({
                "id": ph["id"],
                "description": ph.get("description", ""),
                "rationale": rationale
            })
            return f"Added {phantom_id} to plan."


        def finish_plan(_input: str) -> dict:
            """Finish building the plan and return it as a json."""
            return {"plan": plan}

        # Define your tools
        tools = [
            Tool(name="search_phantoms", func=search_phantoms, description="Search available phantoms by description/tags"),
            Tool(name="add_to_plan", func=add_to_plan, description="Add a phantom to the workflow plan with rationale"),
            Tool(name="finish_plan", func=finish_plan, description="Finish building the plan and return it")
        ]


        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=(
                "You are an AI planner that creates workflows for lead generation.\n\n"
                "Instructions:\n"
                "- Think step by step.\n"
                "- Search for the right phantom if you are not sure.\n"
                "- The typical workflow is: search → enrich → find contact → outreach.\n"
                "- BUT: only include steps that are needed for the goal.\n"
                "- If a single phantom is enough, just add it and finish.\n"
                "- Always keep the order logical (e.g., don’t do outreach before search).\n"
                "- Never invent phantom IDs; use only from the provided list.\n"
                "- When the workflow is complete, call finish_plan.\n"
                "Available tools:\n{tools}\n\n"
                 "Tool names: {tool_names}\n"
            ),
            suffix="Begin!\n\n{agent_scratchpad}",
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
        )

        # ✅ Now create the agent properly
        agent = create_react_agent(llm=self.llm, tools=tools, prompt=prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

        # Run the agent
        result = agent_executor.invoke({"input": goal})

        workflow = result.get("plan", plan)
        print(workflow[0])
        selected = [p for p in self.phantoms if p["id"] in workflow]

        formatted = "\n".join(f"- {p['id']}: {p['description']}" for p in workflow)

        return AIMessage(
            content=f"Here's the proposed plan:\n\n{formatted}",
            additional_kwargs={"plan": workflow}
        )

    def node_user_approval(self, messages, plan=None):
        goal = self.extract_goal(messages)
        plan = plan or []
        approved = present_workflow_to_user(goal, plan)
        if not approved:
            return AIMessage(content="The workflow has is not approved. ", additional_kwargs={"approved": False, "plan": []})
        return AIMessage(content="The workflow has is approved. ", additional_kwargs={"approved": True, "plan": plan})

    def approval_router(self, messages):
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "approved" in msg.additional_kwargs:
                approval_message  = msg.additional_kwargs.get("approved", False)
                return "prepare_inputs" if approved else "plan_workflow"
            else:
                return "plan_workflow"  # fallback

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
        graph.add_node("plan_workflow", self.node_plan_workflow)
        graph.add_node("user_approval", self.node_user_approval)
        graph.add_node("prepare_inputs", self.node_prepare_inputs)
        graph.add_node("execute", self.node_execute)
        graph.add_node("logger", self.node_logger)

        graph.add_edge("plan_workflow", "user_approval")
        # graph.add_edge("user_approval", "prepare_inputs")
        graph.add_conditional_edges("user_approval", self.approval_router)
        graph.add_edge("prepare_inputs", "execute")
        graph.add_edge("execute", "logger")

        graph.set_entry_point("plan_workflow")
        graph.set_finish_point("logger")

        return graph

    # --- Runner ---
    def run(self, messages):
        return self.agent.invoke(
            messages,
            config={"configurable": {"thread_id": str(uuid.uuid4())}}
        )



