from django.urls import path
from orders.views import OrderCreateAPIView,CancelOrderAPIView,OrderAllocationAPIView,BackorderListAPIView

urlpatterns = [
    path("orders/",OrderCreateAPIView.as_view(),name="order-create"),
    path("orders/<int:order_id>/cancel/",CancelOrderAPIView.as_view(),name="cancel-order"),
    path("orders/<int:order_id>/allocation/",OrderAllocationAPIView.as_view(),name="order-allocation"),
    path("backorders/",BackorderListAPIView.as_view(),name="backorder-list")


]