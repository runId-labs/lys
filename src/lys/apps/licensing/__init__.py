"""
Licensing app for subscription management, license plans, and rule-based constraints.

This app provides:
- Freemium model with free and paid tiers
- License plans with versioning for grandfathering
- Rule-based quotas and feature toggles
- Stripe integration for billing
"""
from lys.apps.licensing.registries import ValidatorRegistry, DowngraderRegistry


__registries__ = [
    ValidatorRegistry,
    DowngraderRegistry,
]