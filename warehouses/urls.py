from django.urls import path
from .views import( WarehouseCreateAPIView,
                  WarehouseShippingRateListCreateAPIView,
                    WarehouseShippingRateDetailAPIView,)

urlpatterns = [
    path("warehouses/",WarehouseCreateAPIView.as_view(),name="warehouse-create"),
    path("shipping-rates/",WarehouseShippingRateListCreateAPIView.as_view(),name="shipping-rate-list-create"),
    path("shipping-rates/<int:pk>/",WarehouseShippingRateDetailAPIView.as_view(),name="shipping-rate-detail"),
]