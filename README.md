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
- If 

### Experiments done
- First iteration: The current node is a “one-shot planner.” LLM sees the phantoms, emits a JSON list of IDs.
- Second iteration:The planning node was replaced with a reAct agent. 

With a ReAct agent we have an interactive reasoning loop. 
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


### Future considerations
- Business logic required for building workflows:
    -Prompt Optimization to incorporate workflow logic
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
        -SLMs are less prone to hallucinations as compared to LLMs, they are more likely to admit that they do not know
    -Or a Validator node in the graph to check the plans produced
- Langsmith for tracking prompts
- Guardrails for jailbreak or reducing the risk of hallucinations
- Evaluation mechanisms Arize AI (LLM tool calls, search relevance)
