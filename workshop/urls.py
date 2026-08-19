from django.urls import path

from . import views

urlpatterns = [
    path("payments/callback/", views.payment_callback, name="payment_callback"),
    path("payments/status/<str:reference_id>/", views.payment_status, name="payment_status"),
    path("payments/mock/<str:reference_id>/", views.mock_pay, name="mock_pay"),
    path("webhooks/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
]
