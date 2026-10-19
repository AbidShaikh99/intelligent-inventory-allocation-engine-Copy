from django.db import transaction

from audit.models import InventoryMovement
from products.models import Inventory, Product
from warehouses.models import Warehouse


@transaction.atomic
def update_inventory(
    *,
    warehouse_id,
    product_id,
    available_quantity,
    damaged_quantity,
    reorder_threshold,
    reason,
):
    # Lock the warehouse and product rows.
    # This also serializes creation of inventory for this pair.
    warehouse = Warehouse.objects.select_for_update().get(
        pk=warehouse_id
    )

    product = Product.objects.select_for_update().get(
        pk=product_id
    )

    if not product.is_active:
        raise ValueError("Inactive products cannot receive inventory updates.")

    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse,
        product=product,
        defaults={
            "available_quantity": 0,
            "reserved_quantity": 0,
            "damaged_quantity": 0,
            "reorder_threshold": 0,
        },
    )

    # Lock the inventory record before reading its current quantities.
    inventory = Inventory.objects.select_for_update().get(
        pk=inventory.pk
    )

    old_available = inventory.available_quantity
    old_damaged = inventory.damaged_quantity

    inventory.available_quantity = available_quantity
    inventory.damaged_quantity = damaged_quantity
    inventory.reorder_threshold = reorder_threshold

    inventory.save(
        update_fields=[
            "available_quantity",
            "damaged_quantity",
            "reorder_threshold",
            "updated_at",
        ]
    )

    available_change = available_quantity - old_available
    damaged_change = damaged_quantity - old_damaged

    if created:
        movement_type = InventoryMovement.MovementType.INITIAL_STOCK
    elif damaged_change != 0:
        movement_type = InventoryMovement.MovementType.DAMAGE
    else:
        movement_type = InventoryMovement.MovementType.STOCK_ADJUSTMENT

    InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=movement_type,
        available_change=available_change,
        damaged_change=damaged_change,
        reference=f"INVENTORY-{inventory.pk}",
        reason=reason,
    )

    return inventory