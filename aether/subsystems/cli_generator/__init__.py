"""
aether.subsystems.cli_generator

Generate human-readable CLI usage documentation from an app's config.yaml.
"""

from .generator import CLIUsageGenerator, CLIUsageDocument

__all__ = ["CLIUsageGenerator", "CLIUsageDocument"]