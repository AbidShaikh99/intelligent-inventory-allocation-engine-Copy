from django.db import models


class Order(models.Model):

    class Priority(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        EXPRESS = "EXPRESS", "Express"
        PREMIUM = "PREMIUM", "Premium"
        EMERGENCY = "EMERGENCY", "Emergency"

    class Status(models.TextChoices):
        PENDING_ALLOCATION = (
            "PENDING_ALLOCATION",
            "Pending Allocation",
        )
        ALLOCATION_PLANNED = (
            "ALLOCATION_PLANNED",
            "Allocation Planned",
        )
        RESERVED = "RESERVED", "Reserved"
        BACKORDERED = "BACKORDERED", "Backordered"
        PARTIALLY_SHIPPED = (
            "PARTIALLY_SHIPPED",
            "Partially Shipped",
        )
        SHIPPED = "SHIPPED", "Shipped"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()

    delivery_city = models.CharField(max_length=100)
    delivery_address = models.TextField()

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.STANDARD,
    )

    promised_delivery_at = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_ALLOCATION,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Order #{self.pk} - {self.priority}"


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    quantity = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_product_per_order",
            ),
        ]

    def __str__(self):
        return (
            f"Order #{self.order_id} - "
            f"{self.product.sku} x {self.quantity}"
        )