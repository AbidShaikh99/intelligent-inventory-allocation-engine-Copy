from django.db import models
from django.core.validators import MinValueValidator


class Warehouse(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    name = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)

    processing_capacity = models.PositiveIntegerField()

    storage_restrictions = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.city}"

class WarehouseShippingRate(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="shipping_rates",
    )
    destination_city = models.CharField(max_length=100)

    fixed_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    cost_per_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    transit_hours = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "destination_city"],
                name="unique_warehouse_destination_rate",
            ),
        ]

    def __str__(self):
        return (
            f"{self.warehouse.name} -> {self.destination_city}"
        )