from enum import Enum

class EnvironmentEnum(str, Enum):
    """Application environment enumeration."""
    DEV = "dev"
    PREPROD = "preprod"
    PROD = "prod"
    DEMO = "demo"
