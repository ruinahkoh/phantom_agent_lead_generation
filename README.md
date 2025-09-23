## Context
You just joined PhantomBuster, and the Product team needs your help developing an agentic AI
system to run lead generation efforts for our customers. The engineers already know how to use
our API to run phantoms, but they need help handling the reasoning and execution of actions
based on a user's goal.

## Mission
Design and implement a prototype of an AI agent that can autonomously reason about a goal,
plan actions and simulate the execution of phantoms. This prototype should be able to perform
a series of actions to find and develop leads based on chat-based interactions with a user.

## Overview
This prototype demonstrates an agentic AI system that can reason about a user’s lead generation goal, plan a workflow of PhantomBuster tools, and simulate execution in a human-in-the-loop flow. It shows how LangGraph can orchestrate phantoms step by step using a ReAct-style agent, moving us toward autonomous yet controllable workflows for our customers


## Workflow
1) User inputs the goal
2) The reasoning and acting agent plans the workflow based on the goal and is able to call tools [search_phantoms,add_to_plan,finish_plan]
3) The user approves the plan or regenerates(start from step 1)
4) The user keys in the required inputs for each phantom to execute the phantom
5) All inputs have to be keyed in before a mock execution of phantom workflow (tools)

**The following graph shows the nodes and transitions in the planning/execution loop:**
![graph](https://github.com/ruinahkoh/phantom_agent_lead_generation/blob/main/graph.png)


## Key Features
Explicitly call out what works today (so it’s easy to demo):
- Chat interface to capture user goals (Streamlit)
- Vector search over phantoms (FAISS)
- ReAct planning agent (search_phantoms → add_to_plan → finish_plan)
- Human approval step before execution
- Input collection + mock phantom execution
- Logging of execution results

## Assumptions
- User has knowledge of PhantomBuster phantoms.
- Execution is simulated (mock run, not actual API calls).
- Input format for add_to_plan is phantom_id | rationale.
- Only a subset of workflows tested (lead gen via LinkedIn).


## Experiments done
Iteration 1: One shot planner 
    - The current node is a “one-shot planner.”
    - Search for phantoms according to goal, add the phantoms to the LLM context LLM idenfies phantoms to output a JSON list of IDs.
    - Limitation: brittle, no interactive reasoning


Iteration 2: ReAct agent
    - LLM reasons step by step, calls tools (search_phantoms, add_to_plan, finish_plan).
    - Benefit: more controllable, reduces hallucination, mirrors LangGraph execution model.

**Chose the second iteration to add the interactive reasoning loop**
 
The LLM can iteratively propose:

“I need to find a search tool.”
Then call a search_phantoms tool.
Then “I should enrich the profiles” → call search_phantoms again with enrich.

```
Action: search_phantoms  
Action Input: outreach
LinkedIn Post Engagers to Lead Outreach.js: Start conversations with people who liked or commented on your company page or profile posts.
LinkedIn Group Members to Outreach.js: Reach out to new LinkedIn group members who are curious about what you do.
LinkedIn Outreach.js: Create a full LinkedIn outreach strategy with connection request, introduction message, and up to three follow up messages. This Phantom covers all your LinkedIn Outreach needs in one place.
LinkedIn Search to Outreach.js: Start conversations with leads sourced from a LinkedIn or Sales Navigator search.
HubSpot Contact LinkedIn Outreach.js: Run an outreach campaign on LinkedIn and log the activity in HubSpotThought: The "LinkedIn Outreach.js" phantom looks like a comprehensive outreach tool that covers connection requests, introduction messages, and follow-ups on LinkedIn. It fits well as the outreach step after finding contacts.

Action: add_to_plan  
Action Input: LinkedIn Outreach.js | Use this phantom to perform LinkedIn outreach including connection requests, introduction messages, and follow-ups.
Added LinkedIn Outreach.js to plan.Thought: I have added phantoms for all four steps in the lead generation workflow in the correct order: search, enrich, find contact, and outreach. Now I will finish the plan.

Action: finish_plan  
Action Input: Lead generation workflow with LinkedIn Search to Outreach.js for searching leads, AI LinkedIn Profile Enricher.js for enriching data, Professional Email Finder.js for finding contacts, and LinkedIn Outreach.js for outreach.
```

This allows the agent to build the workflow step by step. This would also mean that the phantom_search would be provided as a tool for the agent to call


## Future considerations
Prompt & Workflow Logic: 
- optimize prompts to enforce logical order while allowing single-step workflows

Model Choices: 
- explore fine-tuning smaller models (SLMs) for planning
   
    -Agent planning could be done by an SLM fine-tuned to create workflows with phantoms. example: (system_prompt, user_prompt, assistant) 
    ```
    {
  "messages": [
    {"role": "system", "content": "You are an AI planner for PhantomBuster workflows."},
    {"role": "user", "content": "Find 50 SaaS marketing managers in Berlin and prepare outreach sequence."},
    {"role": "assistant", "content": "Thought: I should search for a LinkedIn search tool.\nAction: search_phantoms[\"linkedin search\"]\nObservation: linkedin-search-export: ...\nThought: Add linkedin-search-export to plan.\nAction: add_to_plan[\"linkedin-search-export | Search for SaaS marketing managers in Berlin\"]\nObservation: Added linkedin-search-export to plan.\n..."}
     ]
    }
    ```
- SLMs are less prone to hallucinations as compared to LLMs, they are more likely to admit that they do not know

User Interface:
- current UI is simple (streamlit) perhaps a more complex UI with authentication is required for production

Observability: 
- integrate LangSmith for trace logging and evaluation

Guardrails:
- for jailbreak or reducing the risk of hallucinations

Evaluation: 
- Arize AI for tool-call accuracy, LLM as a judge, and search relevance scoring

## Quickstart
1. Clone repository
2. Add a .env file and define your `OPENAI_API_KEY`
3. Set up a virtual environment and install requirements.txt
`pip install -r requirements.txt`
4. Run the application `streamlit run app.py`
