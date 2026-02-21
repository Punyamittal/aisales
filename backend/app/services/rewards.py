"""Reward model for outcomes."""
from ..models.schemas import REWARD_VALUES


def get_reward(category: str, company_multiplier: float = 1.0) -> float:
    """Base reward for outcome category, optionally scaled by company value."""
    base = REWARD_VALUES.get(category, 0)
    return base * company_multiplier
