from django.db import models


class InventoryMovement(models.Model):

    class MovementType(models.TextChoices):
        INITIAL_STOCK = "INITIAL_STOCK", "Initial Stock"
        STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT", "Stock Adjustment"
        RESERVATION = "RESERVATION", "Reservation"
        RELEASE = "RELEASE", "Reservation Release"
        DAMAGE = "DAMAGE", "Damage Adjustment"
        SUPPLIER_RECEIPT = "SUPPLIER_RECEIPT", "Supplier Receipt"
        SHIPMENT = "SHIPMENT", "Shipment Dispatch"

    inventory = models.ForeignKey(
        "products.Inventory",
        on_delete=models.PROTECT,
        related_name="movements",
    )

    movement_type = models.CharField(
        max_length=30,
        choices=MovementType.choices,
    )

    available_change = models.IntegerField(default=0)
    reserved_change = models.IntegerField(default=0)
    damaged_change = models.IntegerField(default=0)

    reference = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.movement_type} - "
            f"Inventory {self.inventory_id}"
        )