"""Local, deterministic AIOps correlation primitives."""

from .correlator import CorrelationConfig, MetricSample, correlate, compare_rules

__all__ = ["CorrelationConfig", "MetricSample", "correlate", "compare_rules"]
