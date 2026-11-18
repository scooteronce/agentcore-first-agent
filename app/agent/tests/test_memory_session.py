from unittest.mock import patch

import memory.session as session


def test_returns_none_when_memory_id_unset():
    # MEMORY_ID is read from the environment at import time, so patch the
    # module attribute rather than the environment.
    with patch.object(session, "MEMORY_ID", None):
        assert session.get_memory_session_manager("s1", "alice") is None


def test_builds_manager_with_per_actor_namespaces():
    with patch.object(session, "MEMORY_ID", "mem-123"), \
         patch.object(session, "REGION", "us-west-2"), \
         patch.object(session, "AgentCoreMemorySessionManager") as manager_cls:
        session.get_memory_session_manager("s1", "alice")

    (config, region) = manager_cls.call_args.args
    assert region == "us-west-2"
    assert config.memory_id == "mem-123"
    assert config.session_id == "s1"
    assert config.actor_id == "alice"
    assert set(config.retrieval_config) == {"/users/alice/facts", "/episodes/alice/s1"}
