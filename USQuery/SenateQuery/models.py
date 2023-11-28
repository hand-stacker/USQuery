from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API

class Senator(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    full_name = models.CharField(max_length=40)
    
class Congress(models.Model):
    congress_num = models.IntegerField(primary_key=True)
    senators = models.ManyToManyField(Senator, through="Senatorship")
    
class Senatorship(models.Model):
    senator = models.ForeignKey(Senator, on_delete=models.CASCADE)
    congress = models.ForeignKey(Congress, on_delete=models.CASCADE)
    state = models.CharField(max_length=2)
