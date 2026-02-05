from __future__ import annotations

from app.ambio_ai_strategy.bad_strategy import BadStrategy
from app.ambio_ai_strategy.generator_strategy import GeneratorStrategy
from app.ambio_ai_strategy.registry import STRATEGY_REGISTRY


def choose_strategy(mode: str | None) -> GeneratorStrategy:
    m = (mode or "chat").strip().lower()
    cls = STRATEGY_REGISTRY.get(m)
    if not cls:
        return BadStrategy(invalid_mode=m)
    return cls()

