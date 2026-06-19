# Prompt Assets

## Core Ideas

To optimize for KV-cache, we'd like to reduce change in prompts
throughout execution, even for subagents. We're to use the concept of
'layers' to introduce things.

Layers are ordered from _most_ to _least_ static information.

The layers are:

1. `base-prompt` - Core harness situation prompt for all agents
   - situates agent in harness
   - displays _core_ capabilities (least prone to overrides in session)
     - file operations
     - question tool, cross-agent comms
2. `user-base-prompt` - Base prompt given by the user to be appended
   at this stage (thus, for all agents)
3. `agent-prompt` - Agent prompt - this will define customizations for
   agent archetypes and overrides, (e.g.: exploratory agent, planner,
   researcher, etc.)
   - specific instructions for different types of tasks dependending
     on the agent archetype.
   - agent-specific capabilities like web search for
     exploratory-leaning agents and so on
4. `user-agent-prompt` - Agent-specific user prompt provided by user
   to be appended at this stage (thus, only for this type of agent).
5. `session-prompt` - Session-specific tweaks/overrides/context
   - User query, compaction hand-off, etc.
     - Compaction should be structured to expand on 1st section (which
       is user query) - further compactions should attempt to expand
       as most as possible from past compactions - if possible.
   - Any extra capabilities given to agent that aren't derived from
     'base' or 'agent' capabilities.
