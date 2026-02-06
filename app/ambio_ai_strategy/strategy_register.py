from __future__ import annotations

from app.ambio_ai_strategy.chat_strategy import ChatStrategy
from app.ambio_ai_strategy.image_analysis_strategy import ImageAnalysisStrategy
from app.ambio_ai_strategy.image_strategy import ImageStrategy
from app.ambio_ai_strategy.registry import register_strategies

register_strategies(ChatStrategy, ImageAnalysisStrategy, ImageStrategy)

