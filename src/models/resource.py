"""Resource model and inventory management."""

from typing import Dict

from pydantic import BaseModel, Field

from .enums import ResourceType


class ResourceInventory(BaseModel):
    """Manages a collection of resources."""

    resources: Dict[ResourceType, int] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize all resource types to 0 if not provided
        for resource_type in ResourceType:
            if resource_type not in self.resources:
                self.resources[resource_type] = 0

    def add(self, resource_type: ResourceType, amount: int) -> None:
        """Add resources to inventory."""
        if resource_type not in self.resources:
            self.resources[resource_type] = 0
        self.resources[resource_type] += amount

    def remove(self, resource_type: ResourceType, amount: int) -> bool:
        """
        Remove resources from inventory.

        Returns True if successful, False if insufficient resources.
        """
        if resource_type not in self.resources:
            self.resources[resource_type] = 0

        if self.resources[resource_type] >= amount:
            self.resources[resource_type] -= amount
            return True
        return False

    def has(self, resource_type: ResourceType, amount: int) -> bool:
        """Check if inventory has enough of a resource."""
        return self.resources.get(resource_type, 0) >= amount

    def has_multiple(self, requirements: Dict[ResourceType, int]) -> bool:
        """Check if inventory has enough of multiple resources."""
        return all(
            self.has(resource_type, amount)
            for resource_type, amount in requirements.items()
        )

    def remove_multiple(self, requirements: Dict[ResourceType, int]) -> bool:
        """
        Remove multiple resources from inventory.

        Returns True if successful, False if insufficient resources.
        """
        if not self.has_multiple(requirements):
            return False

        for resource_type, amount in requirements.items():
            self.remove(resource_type, amount)

        return True

    def get(self, resource_type: ResourceType) -> int:
        """Get the amount of a specific resource."""
        return self.resources.get(resource_type, 0)

    def to_dict(self) -> Dict[str, int]:
        """Convert inventory to a simple dictionary."""
        return {rt.value: amount for rt, amount in self.resources.items()}

    def __repr__(self) -> str:
        return f"ResourceInventory({self.to_dict()})"

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
