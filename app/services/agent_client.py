from typing import Iterator, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from app.config import FOUNDRY_AGENT_NAME, FOUNDRY_PROJECT_ENDPOINT

_credential: Optional[DefaultAzureCredential] = None
_project_client: Optional[AIProjectClient] = None
_openai_client = None


def startup() -> None:
    global _credential, _project_client, _openai_client
    _credential = DefaultAzureCredential()
    _project_client = AIProjectClient(
        endpoint=FOUNDRY_PROJECT_ENDPOINT,
        credential=_credential,
        allow_preview=True,
    )
    _openai_client = _project_client.get_openai_client(agent_name=FOUNDRY_AGENT_NAME)


def shutdown() -> None:
    if _project_client is not None:
        _project_client.close()
    if _credential is not None:
        _credential.close()


def create_conversation() -> str:
    conversation = _openai_client.conversations.create()
    return conversation.id


def stream_reply(user_message: str, conversation_id: str) -> Iterator[str]:
    stream = _openai_client.responses.create(
        conversation=conversation_id,
        input=[{"role": "user", "content": user_message}],
        stream=True,
    )
    for event in stream:
        if getattr(event, "type", "") == "response.output_text.delta":
            yield event.delta
