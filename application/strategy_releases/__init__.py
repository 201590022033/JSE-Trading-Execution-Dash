"""Inactive StrategyRelease compatibility/evaluation. Import never activates."""
from .evaluator import InactiveStrategy, StrategyError, StrategyEvaluator

__all__ = ['InactiveStrategy', 'StrategyError', 'StrategyEvaluator']
