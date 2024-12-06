from django.contrib import admin
from .models import Vote, ChoiceVote, Choice

# Register your models here.
admin.site.register(Vote)
admin.site.register(ChoiceVote)
admin.site.register(Choice)
