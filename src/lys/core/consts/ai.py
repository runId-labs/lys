from enum import Enum


class ToolRiskLevel(Enum):
    """Risk level for AI tool operations.

    Used to determine if confirmation is required before executing a tool.
    """
    READ = "read"       # Safe - no confirmation needed
    CREATE = "create"   # New data - requires confirmation
    UPDATE = "update"   # Modification - requires confirmation
    DELETE = "delete"   # Deletion - requires confirmation