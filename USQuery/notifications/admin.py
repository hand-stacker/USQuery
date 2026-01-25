from django.contrib import admin

from .models import Device, StarredBill, StarredMembership, FavoriteSubject

admin.site.register(Device)
admin.site.register(StarredBill)
admin.site.register(StarredMembership)
admin.site.register(FavoriteSubject)