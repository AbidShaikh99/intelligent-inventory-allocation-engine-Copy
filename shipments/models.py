from django.db import models


class Shipment(models.Model):

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        READY = "READY", "Ready for Dispatch"
        DISPATCHED = "DISPATCHED", "Dispatched"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    allocation_plan = models.ForeignKey(
        "allocation.AllocationPlan",
        on_delete=models.PROTECT,
        related_name="shipments",
    )

    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="shipments",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )

    tracking_number = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    estimated_delivery_at = models.DateTimeField()

    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["allocation_plan", "warehouse"],
                name="unique_plan_warehouse_shipment",
            )
        ]

    def __str__(self):
        return (
            f"Shipment #{self.pk} - "
            f"Plan #{self.allocation_plan_id} - "
            f"Warehouse #{self.warehouse_id}"
        )
