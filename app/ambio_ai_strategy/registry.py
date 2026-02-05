from __future__ import annotations

from typing import Type

from app.ambio_ai_strategy.generator_strategy import GeneratorStrategy

STRATEGY_REGISTRY: dict[str, Type[GeneratorStrategy]] = {}


def register_strategies(*strategy_classes: Type[GeneratorStrategy]) -> None:
    for cls in strategy_classes:
        for p in cls().purpose():
            STRATEGY_REGISTRY[p] = cls

