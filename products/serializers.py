from rest_framework import serializers

from .models import Product, Inventory


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "weight_kg",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_weight_kg(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Product weight cannot be negative."
            )
        return value


class InventorySerializer(serializers.ModelSerializer):

    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )

    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )

    physical_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "product",
            "product_sku",
            "available_quantity",
            "reserved_quantity",
            "damaged_quantity",
            "physical_quantity",
            "reorder_threshold",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reserved_quantity",
            "physical_quantity",
            "created_at",
            "updated_at",
        ]


class InventoryUpdateSerializer(serializers.Serializer):

    available_quantity = serializers.IntegerField(min_value=0)
    damaged_quantity = serializers.IntegerField(min_value=0)
    reorder_threshold = serializers.IntegerField(min_value=0)

    reason = serializers.CharField(
        max_length=500,
        allow_blank=False,
    )