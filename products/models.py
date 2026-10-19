from django.db import models


class Product(models.Model):
    sku = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(max_length=150)

    weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sku} - {self.name}"

class Inventory(models.Model):

    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="inventory_records",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_records",
    )

    available_quantity = models.PositiveIntegerField(default=0)

    reserved_quantity = models.PositiveIntegerField(default=0)

    damaged_quantity = models.PositiveIntegerField(default=0)

    reorder_threshold = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "product"],
                name="unique_warehouse_product_inventory",
            ),
        ]

    @property
    def physical_quantity(self):
        return (
            self.available_quantity
            + self.reserved_quantity
            + self.damaged_quantity
        )

    def __str__(self):
        return f"{self.warehouse.name} - {self.product.sku}"