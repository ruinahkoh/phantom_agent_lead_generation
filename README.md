### Context
You just joined PhantomBuster, and the Product team needs your help developing an agentic AI
system to run lead generation efforts for our customers. The engineers already know how to use
our API to run phantoms, but they need help handling the reasoning and execution of actions
based on a user's goal.

### Mission
Design and implement a prototype of an AI agent that can autonomously reason about a goal,
plan actions and simulate the execution of phantoms. This prototype should be able to perform
a series of actions to find and develop leads based on chat-based interactions with a user.

### Workflow
1) User inputs the goal
2) The reasoning and acting agent plans the workflow based on the goal and is able to call tools [search_phantoms,add_to_plan,finish_plan]
3) The user approves the plan or regenerates(start from step 1)
4) The user keys in the required inputs for each phantom to execute the phantom
5) All inputs have to be keyed in before a mock execution of phantom workflow (tools)

![graph](https://github.com/ruinahkoh/phantom_agent_lead_generation/blob/main/graph.png)


### Assumptions
- The workflow will follow a structure: search → enrich → find contact → outreach.

### Experiments done
- First iteration: The current node is a “one-shot planner.” LLM sees the phantoms, emits a JSON list of IDs.
- Second iteration:The planning node was replaced with a reAct agent. 

With a ReAct agent we have an interactive reasoning loop. 
The LLM can iteratively propose:

“I need to find a search tool.”
Then call a search_phantoms tool.
Then “I should enrich the profiles” → call search_phantoms again with enrich.

This allows the agent to build the workflow step by step. This would also mean that the phantom_search would be provided as a tool for the agent to call


### Future considerations
- Agent planning could be done by an SLM fine-tuned to create workflows with phantoms. example: (User goal, reasoning, phantoms_identified) 
- Or it can search for pre-created workflows in a vector database right away.
- Langsmith for tracking prompts
- Guardrails for jailbreak
- Evaluation mechanisms Arize AI (LLM tool calls, search relevance)
