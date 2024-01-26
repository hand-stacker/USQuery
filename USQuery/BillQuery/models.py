from django.db import models
from SenateQuery import models as SQmodels

# Create your models here.
class Bill(models.Model):
    id = models.CharField(primary_key=True, max_length=15)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    house = models.Choices("House", "Representative")
    votes_in_favor = models.ManyToManyField(SQmodels.Member)
    