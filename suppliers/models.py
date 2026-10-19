
from django.db import models
from django.core.validators import MinValueValidator


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SupplierPurchaseOrder(models.Model):

    class Status(models.TextChoices):
        ORDERED = "ORDERED", "Ordered"
        PARTIALLY_RECEIVED = (
            "PARTIALLY_RECEIVED",
            "Partially Received",
        )
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_orders",
    )

    expected_delivery_at = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ORDERED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Purchase Order #{self.pk}"


class SupplierPurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        SupplierPurchaseOrder,
        on_delete=models.PROTECT,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_order_items",
    )

    ordered_quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    received_quantity = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "product"],
                name="unique_product_per_supplier_purchase_order",
            ),
            models.CheckConstraint(
                condition=models.Q(ordered_quantity__gt=0),
                name="supplier_po_ordered_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    received_quantity__lte=models.F("ordered_quantity")
                ),
                name="supplier_po_received_not_above_ordered",
            ),
        ]

    def __str__(self):
        return (
            f"PO #{self.purchase_order_id} - "
            f"{self.product.sku} x {self.ordered_quantity}"
        )
