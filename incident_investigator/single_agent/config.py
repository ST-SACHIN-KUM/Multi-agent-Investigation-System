"""Independent LLM request and overall limits for the sequential baseline."""
from dataclasses import dataclass
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from incident_agents.state import Config


@dataclass
class SingleAgentConfig(Config):
    llm_timeout: float = 90.0
    max_llm_retries: int = 1
    wall_clock: float = 600.0

    def __post_init__(self):
        if self.llm_timeout <= 0 or self.wall_clock <= 0:
            raise ValueError("LLM timeout and wall-clock limit must be positive")
        if self.max_llm_retries < 0:
            raise ValueError("LLM retry count must be nonnegative")
