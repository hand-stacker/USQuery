from django.contrib import admin

from .models import UserProfile, EmailVerification

admin.site.register(UserProfile)
admin.site.register(EmailVerification)
