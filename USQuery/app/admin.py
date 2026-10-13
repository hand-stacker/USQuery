from django.contrib import admin

from .models import UserProfile, EmailVerification, BillChunk, ApiUsageEvent, InfrastructureCost

admin.site.register(UserProfile)
admin.site.register(EmailVerification)
admin.site.register(BillChunk)


@admin.register(InfrastructureCost)
class InfrastructureCostAdmin(admin.ModelAdmin):
    list_display = ('month', 'name', 'amount_usd')
    list_filter = ('month',)
    ordering = ('-month', 'name')


@admin.register(ApiUsageEvent)
class ApiUsageEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'service', 'purpose', 'input_tokens', 'output_tokens')
    list_filter = ('service', 'purpose')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)