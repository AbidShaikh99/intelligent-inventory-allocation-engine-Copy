
from rest_framework import serializers

from audit.models import InventoryMovement


class InventoryMovementSerializer(serializers.ModelSerializer):
    inventory_id = serializers.IntegerField(
        source="inventory.id",
        read_only=True,
    )
    warehouse_id = serializers.IntegerField(
        source="inventory.warehouse_id",
        read_only=True,
    )
    product_id = serializers.IntegerField(
        source="inventory.product_id",
        read_only=True,
    )

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "inventory_id",
            "warehouse_id",
            "product_id",
            "movement_type",
            "available_change",
            "reserved_change",
            "damaged_change",
            "reference",
            "reason",
            "created_at",
        ]
        read_only_fields = fields
