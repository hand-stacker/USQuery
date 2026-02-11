from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.api_register, name='api-register'),
    path('verify-email/', views.api_verify_email, name='api-verify-email'),
    path('resend-verification/', views.api_resend_verification, name='api-resend-verification'),
    path('login/', views.api_login, name='api-login'),
    path(
        "password-reset-api/",
        views.api_reset_password.as_view(),
        name="api-password-reset",
    ),

]