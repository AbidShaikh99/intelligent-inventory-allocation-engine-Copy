from django.urls import path

from allocation.views import (OrderAllocationAPIView, ReserveAllocationPlanAPIView, OrderAllocationAPIView, AllocationRebalanceAPIView,
AllocationDecisionAPIView)

urlpatterns = [
    path("orders/<int:order_id>/allocate/",OrderAllocationAPIView.as_view(),name="order-allocation"),
    path("plans/<int:plan_id>/reserve/",ReserveAllocationPlanAPIView.as_view(),name="reserve-allocation-plan"),
    path("rebalance/",AllocationRebalanceAPIView.as_view(),name="allocation-rebalance"),
    path("decisions/<int:plan_id>/",AllocationDecisionAPIView.as_view(),name="allocation-decision-detail"),
    
]