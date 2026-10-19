from django.urls import path

from audit.views import InventoryMovementListAPIView

urlpatterns = [
    path(
        "movements/",
        InventoryMovementListAPIView.as_view(),
        name="inventory-movements",
    ),
]
