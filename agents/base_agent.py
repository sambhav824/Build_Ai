import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any
from api.schemas.protocol import AgentRequest, AgentResponse
from utils.logging_config import logger

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process the structured request and return an AgentResponse.
        Must not raise uncaught exceptions to caller.
        """
        pass

    def create_error_response(self, request: AgentRequest, error_message: str) -> AgentResponse:
        logger.error(f"Agent {self.name} failed processing exec {request.execution_id}: {error_message}")
        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="failed",
            result={},
            warnings=[f"Execution failed in {self.name}"],
            requires_approval=False,
            error=error_message
        )
