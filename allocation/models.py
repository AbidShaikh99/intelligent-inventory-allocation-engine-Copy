from django.core.validators import MinValueValidator
from django.db import models


class AllocationPlan(models.Model):

    class Status(models.TextChoices):
        FULL = "FULL", "Fully Allocated"
        PARTIAL = "PARTIAL", "Partially Allocated"
        INFEASIBLE = "INFEASIBLE", "No Feasible Allocation"

    class ReservationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Reservation"
        RESERVED = "RESERVED", "Stock Reserved"
        RELEASED = "RELEASED", "Reservation Released"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="allocation_plans",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    reservation_status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )

    total_shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    requested_units = models.PositiveIntegerField(default=0)
    allocated_units = models.PositiveIntegerField(default=0)
    shipment_count = models.PositiveIntegerField(default=0)

    decision_details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Allocation Plan #{self.pk} - Order #{self.order_id}"



class AllocationLine(models.Model):

    plan = models.ForeignKey(
        AllocationPlan,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="allocation_lines",
    )

    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="allocation_lines",
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    estimated_delivery_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "order_item", "warehouse"],
                name="unique_plan_item_warehouse",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="allocation_line_quantity_positive",
            ),
        ]

    def __str__(self):
        return (
            f"Plan #{self.plan_id}: "
            f"Item #{self.order_item_id}, "
            f"Warehouse #{self.warehouse_id}, "
            f"Qty {self.quantity}"
        )
    
