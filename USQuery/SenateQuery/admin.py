from django.contrib import admin
from .models import Congress, Member, Senatorship, Representativeship

admin.site.register(Congress)
admin.site.register(Member)
admin.site.register(Senatorship)
admin.site.register(Representativeship)
# Register your models here.
