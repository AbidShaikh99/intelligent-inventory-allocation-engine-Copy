from django.urls import path

from .views import SupplierPurchaseOrderCreateAPIView,SupplierCreateAPIView,ReceiveSupplierPurchaseOrderAPIView


urlpatterns = [
    path("purchase-orders/",SupplierPurchaseOrderCreateAPIView.as_view(),name="supplier-purchase-order-create"),
    path("create/",SupplierCreateAPIView.as_view(),name="supplier-create"),
    path("purchase-orders/<int:pk>/receive/",ReceiveSupplierPurchaseOrderAPIView.as_view(),name="supplier-purchase-order-receive"),
]
