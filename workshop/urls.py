from django.urls import path

from . import views

urlpatterns = [
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
    path("payments/callback/", views.payment_callback, name="payment_callback"),
    path(
        "payments/status/<str:reference_id>/poll/",
        views.payment_status_poll,
        name="payment_status_poll",
    ),
    path("payments/status/<str:reference_id>/", views.payment_status, name="payment_status"),
    path("payments/mock/<str:reference_id>/", views.mock_pay, name="mock_pay"),
    path("webhooks/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
    path(
        "webhooks/razorpay/health",
        views.razorpay_webhook_health,
        name="razorpay_webhook_health",
    ),
    path("cron/reminders/", views.cron_reminders, name="cron_reminders"),
    path("cron/reminders", views.cron_reminders, name="cron_reminders_noslash"),
    path(
        "staff/registrations/<int:pk>/mark-paid/",
        views.admin_mark_paid,
        name="admin_mark_paid",
    ),
]
