from __future__ import annotations

from contextlib import contextmanager
import json

from app import agent as agent_module


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []
        self.observations: list[RecordingObservation] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        observation = RecordingObservation(kwargs)
        self.observations.append(observation)
        yield observation


class RecordingObservation:
    def __init__(self, creation: dict) -> None:
        self.creation = creation
        self.updates: list[dict] = []

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self


def test_agent_records_prompt_version_with_v4_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain traces",
        correlation_id="req-12345678",
    )

    span_update = client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is client.prompt

    retrieval, generation = client.observations
    assert retrieval.creation["name"] == "retrieval"
    assert retrieval.creation["as_type"] == "retriever"
    assert retrieval.updates[-1]["output"]["document_count"] == 1

    assert generation.creation["name"] == "generation"
    assert generation.creation["as_type"] == "generation"
    assert generation.creation["model"] == "claude-sonnet-4-5"
    assert generation.creation["prompt"] is client.prompt
    generation_update = generation.updates[-1]
    assert generation_update["usage_details"]["input_tokens"] > 0
    assert generation_update["usage_details"]["output_tokens"] > 0
    assert generation_update["cost_details"]["total"] > 0
    assert generation_update["metadata"]["correlation_id"] == "req-12345678"


def test_trace_observations_only_capture_scrubbed_previews(monkeypatch) -> None:
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: False)

    @contextmanager
    def record_attributes(**kwargs):
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student@vinuni.edu.vn",
        feature="monitoring",
        session_id="session-student@vinuni.edu.vn",
        message="Contact student@vinuni.edu.vn or 090 123 4567 about monitoring",
        correlation_id="req-87654321",
    )

    serialized_observations = json.dumps(
        [
            {"creation": item.creation, "updates": item.updates}
            for item in client.observations
        ],
        default=str,
    )
    assert "student@vinuni.edu.vn" not in serialized_observations
    assert "090 123 4567" not in serialized_observations
    assert "[REDACTED_EMAIL]" in serialized_observations
    assert "[REDACTED_PHONE_VN]" in serialized_observations
