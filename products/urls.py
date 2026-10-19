from django.urls import path

from .views import (
    InventoryUpdateAPIView,
    ProductCreateAPIView,
)

urlpatterns = [
    path("products/",ProductCreateAPIView.as_view(),name="product-create"),
    path("warehouses/<int:warehouse_id>/inventory/<int:product_id>",InventoryUpdateAPIView.as_view(),name="inventory-update"),
]