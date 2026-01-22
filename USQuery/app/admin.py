from django.contrib import admin

from .models import UserProfile, EmailVerification, StarredMember, FavoriteSubjects

admin.site.register(UserProfile)
admin.site.register(EmailVerification)
admin.site.register(StarredMember)
admin.site.register(FavoriteSubjects)
