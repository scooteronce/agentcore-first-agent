import json
import urllib.request
from functools import lru_cache

from strands import Agent, tool
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from parse import parse_payload
from memory.session import get_memory_session_manager

DEFAULT_SYSTEM_PROMPT = (
    "You are an AWS operations assistant. Use the check_aws_health tool to "
    "answer questions about AWS service health and ongoing incidents. Be "
    "specific about regions, services, and timestamps."
)

# The hardcoded path for aws health
HEALTH_FEED_URL = "https://health.aws.amazon.com/public/currentevents"

# Define the collection of tools used by the selected model
tools = []

@tool
def check_aws_health(region: str = "") -> str:
    """Check the AWS Health Dashboard for ongoing service issues.

    Args:
        region: Optional AWS region code (e.g. "us-east-1") to filter by.
            Leave empty to report incidents across all regions.

    Returns:
        A summary of current AWS incidents, or confirmation that none are ongoing.
    """
    try:
        with urllib.request.urlopen(HEALTH_FEED_URL, timeout=10) as resp:
            events = json.loads(resp.read().decode("utf-16"))
    except Exception as exc:
        # a simple exception in case it cant find what its looking for
        return f"Could not reach the AWS Health feed: {exc}"

    # I had to do some fooling around here until I got it right.
    if region:
        needle = region.lower()
        events = [
            e for e in events
            if needle in e.get("arn", "").lower() or needle in e.get("service", "").lower()
        ]

    if not events:
        scope = f"in {region}" if region else "across all regions"
        return f"No ongoing AWS incidents {scope} per the AWS Health Dashboard."

    # an array of events will be stored in lines
    lines = []
    for event in events:
        latest = max(event.get("event_log", []), key=lambda e: e.get("timestamp", 0), default={})
        lines.append(
            f"- {event.get('service_name', 'Unknown service')}"
            f" [{event.get('region_name', 'unknown region')}]:"
            f" {event.get('summary', 'no summary')}."
            f" Latest update: {latest.get('message', 'none')}"
        )
    return f"{len(lines)} ongoing AWS incident(s):\n" + "\n".join(lines)

tools.append(check_aws_health)

def _make_conversation_manager():
    return NullConversationManager()

# doing a little bit of caching
@lru_cache(maxsize=128)
def _get_agent(session_id: str, actor_id: str) -> Agent:
    """Given a session_id and actor_id, return or construct the corresponding Strands agent.
    Note: caching helps avoid repeated identity fetches on non-bedrock model loads
    and supports in-memory session management for local dev."""
    return Agent(
        model=load_model(),
        session_manager=get_memory_session_manager(session_id, actor_id),
        conversation_manager=_make_conversation_manager(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=tools,
    )

def create_app():
    app = BedrockAgentCoreApp()
    log = app.logger

    @app.entrypoint
    async def invoke(payload, context):
        log.info("Invoking Agent.....")

        session_id = getattr(context, "session_id", None) or "default-session"
        prompt, actor_id = parse_payload(payload)

        log.info(f"Invoking with session_id={session_id} and actor_id={actor_id}")
        agent = _get_agent(session_id, actor_id)

        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict) or "event" not in event:
                continue
            cbs = event["event"].get("contentBlockStart")
            if cbs is not None and not cbs.get("start"):
                continue
            yield event

    return app

app = create_app()
if __name__ == "__main__":
    app.run()
