from rest_framework import serializers

from allocation.models import AllocationPlan, AllocationLine


class AllocationRequestSerializer(serializers.Serializer):
    max_shipments = serializers.IntegerField(
        min_value=1,
        max_value=20,
        required=False,
        default=2,
    )


class AllocationLineSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(
        source="order_item.product.sku",
        read_only=True,
    )
    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )

    class Meta:
        model = AllocationLine
        fields = [
            "id",
            "order_item",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "quantity",
            "shipping_cost",
            "estimated_delivery_at",
        ]
        read_only_fields = fields


class AllocationPlanSerializer(serializers.ModelSerializer):
    lines = AllocationLineSerializer(many=True, read_only=True)

    class Meta:
        model = AllocationPlan
        fields = [
            "id",
            "order",
            "status",
            "requested_units",
            "allocated_units",
            "shipment_count",
            "total_shipping_cost",
            "decision_details",
            "lines",
            "reservation_status",
            "created_at",
        ]
        read_only_fields = fields


class ReservationRequestSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=True)

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError(
                "Reservation must be explicitly confirmed."
            )
        return value