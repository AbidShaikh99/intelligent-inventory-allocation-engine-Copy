
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from orders.models import Order, OrderItem
from products.models import Product
from warehouses.models import Warehouse, Inventory
from allocation.models import AllocationPlan, AllocationLine
from allocation.services import reserve_allocation_plan
from audit.models import InventoryMovement


class AllocationReservationTests(TestCase):

    def setUp(self):
        # 1. Create a warehouse.
        self.warehouse = Warehouse.objects.create(
            name="Test Warehouse",
            city="Ahmedabad",
            address="Test Address",
            processing_capacity=100,
            status=Warehouse.Status.ACTIVE,
        )

        # 2. Create a product.
        self.product = Product.objects.create(
            sku="TEST-001",
            name="Test Product",
            weight_kg=Decimal("2.00"),
            is_active=True,
        )

        # 3. Create inventory with 20 available units.
        self.inventory = Inventory.objects.create(
            warehouse=self.warehouse,
            product=self.product,
            available_quantity=20,
            reserved_quantity=0,
            damaged_quantity=0,
            reorder_threshold=5,
        )

        # 4. Create an order ready for reservation.
        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_email="test@example.com",
            delivery_city="Ahmedabad",
            delivery_address="Customer Address",
            status=Order.Status.ALLOCATION_PLANNED,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
        )

        # 5. Create a fully allocated plan.
        self.plan = AllocationPlan.objects.create(
            order=self.order,
            status=AllocationPlan.Status.FULL,
            reservation_status=(
                AllocationPlan.ReservationStatus.PENDING
            ),
            total_shipping_cost=Decimal("100.00"),
            requested_units=5,
            allocated_units=5,
            shipment_count=1,
            decision_details={},
        )

        AllocationLine.objects.create(
            plan=self.plan,
            order_item=self.order_item,
            warehouse=self.warehouse,
            quantity=5,
            shipping_cost=Decimal("100.00"),
            estimated_delivery_at=(
                timezone.now() + timedelta(hours=2)
            ),
        )

    def test_reservation_moves_stock_correctly(self):
        reserve_allocation_plan(self.plan.id)

        self.inventory.refresh_from_db()
        self.plan.refresh_from_db()

        self.assertEqual(self.inventory.available_quantity, 15)
        self.assertEqual(self.inventory.reserved_quantity, 5)

        self.assertEqual(
            self.plan.reservation_status,
            AllocationPlan.ReservationStatus.RESERVED,
        )

        movement = InventoryMovement.objects.filter(
            reference=f"ALLOCATION-{self.plan.id}"
        )

        # Adapt the reference filter to the exact reference
        # your reservation service writes.
        self.assertTrue(
            InventoryMovement.objects.filter(
                inventory=self.inventory,
                movement_type=(
                    InventoryMovement.MovementType.RESERVATION
                ),
                available_change=-5,
                reserved_change=5,
            ).exists()
        )

    def test_reservation_cannot_be_applied_twice(self):
        reserve_allocation_plan(self.plan.id)

        with self.assertRaises(ValueError):
            reserve_allocation_plan(self.plan.id)

        self.inventory.refresh_from_db()

        # The second call must not reserve the same 5 units again.
        self.assertEqual(self.inventory.available_quantity, 15)
        self.assertEqual(self.inventory.reserved_quantity, 5)
