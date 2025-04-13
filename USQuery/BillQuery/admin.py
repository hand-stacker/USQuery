from django.contrib import admin
from .models import Bill, Vote, ChoiceVote, Choice, BillSummary

# Register your models here.
admin.site.register(Vote)
admin.site.register(ChoiceVote)
admin.site.register(Choice)
admin.site.register(Bill)
admin.site.register(BillSummary)
