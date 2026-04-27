from enum import StrEnum


class HistoryMessageRole(StrEnum):
    """Role of author in a history message."""

    SYSTEM = "system"
    """System-related message, directly by harness.

    Can be system prompt, info unrelated to tool execution, and so on.
    """

    USER = "user"
    """Message by user, when convo is directly with user."""

    AGENT_OTHER = "agent_other"
    """Message by other agent, when convo. is with another agent."""

    AGENT_SELF = "agent_self"
    """Message by self (current agent.)

    Text/content parts only.
    """

    AGENT_SELF_THINKING = "agent_self_thinking"
    """Thinking-part of agent response."""

    TOOL_CALL = "tool_call"
    """Tool call by self."""

    TOOL_REPLY = "tool_reply"
    """Tool call response."""

    TOOL_RETRY = "tool_try"
    """Tool call failure response."""

    FILE_SELF = "file_self"
    """File sent from self (agent response.)"""

    FILE_OTHER = "file_other"
    """File sent from other party (user/agent.)"""
