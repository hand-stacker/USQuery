from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API

class Senator(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    full_name = models.CharField(max_length=40)
    def __str__(self):
        return self.full_name
    
class Congress(models.Model):
    congress_num = models.IntegerField(primary_key=True)
    senators = models.ManyToManyField(Senator, through="Senatorship")
    def __str__(self):
        return str(self.congress_num)
    
class Senatorship(models.Model):
    senator = models.ForeignKey(Senator, on_delete=models.CASCADE)
    congress = models.ForeignKey(Congress, on_delete=models.CASCADE)
    state = models.CharField(max_length=2)
    def __str__(self):
        return "Congress :"  + self.congress + " State:" + self.state + " Senator:" + self.senator
