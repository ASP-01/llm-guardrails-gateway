"""FastAPI front door. Run:  uvicorn guardrails_gateway.app:app --reload"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .gateway import Gateway
from .policy import Policy
from .providers import AnthropicProvider, DemoProvider, LLMProvider

log = logging.getLogger("guardrails_gateway")

DEFAULT_POLICY = Path(__file__).resolve().parent.parent / "policies" / "default.yaml"


class PolicyStore:
    """Reloads the YAML when the file changes, so editing the policy needs no redeploy.
    If a new version is invalid, the last good policy keeps running."""

    def __init__(self, path: Path):
        self.path = path
        self._mtime = 0.0
        self.policy = Policy.from_yaml(path)
        self._mtime = path.stat().st_mtime

    def current(self) -> Policy:
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            self._mtime = mtime
            try:
                self.policy = Policy.from_yaml(self.path)
                log.info("policy reloaded: %s", self.policy.name)
            except Exception as e:  # noqa: BLE001
                log.error("policy reload failed, keeping previous version: %s", e)
        return self.policy


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)


def create_app(policy_path: Path | None = None, provider: LLMProvider | None = None) -> FastAPI:
    store = PolicyStore(Path(policy_path or os.getenv("POLICY_PATH", DEFAULT_POLICY)))
    if provider is None:
        provider = AnthropicProvider() if os.getenv("ANTHROPIC_API_KEY") else DemoProvider()

    app = FastAPI(title="LLM Guardrails Gateway")

    @app.get("/health")
    def health():
        return {"ok": True, "policy": store.current().name, "provider": type(provider).__name__}

    @app.get("/v1/policy")
    def policy():
        return store.current().model_dump(by_alias=True)

    @app.post("/v1/chat")
    def chat(req: ChatRequest):
        gw = Gateway(store.current(), provider)
        return gw.run(req.message, [m.model_dump() for m in req.history]).to_dict()

    return app


app = create_app()
