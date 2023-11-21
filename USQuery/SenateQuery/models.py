from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API
class Senator(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    first_name = models.CharField(max_length=20)
    middle_name = models.CharField(max_length=20, null=True)
    last_name = models.CharField(max_length=20)
    suffix = models.CharField(max_length=5, null=True)
    gender = models.CharField(max_length=2)
    birth_date = models.DateField()
    # socials
    url = models.CharField(max_length=50, null=True)
    twitter_user = models.CharField(max_length=15, null=True)
    facebook_user = models.CharField(max_length=50, null=True)
    youtube_user = models.CharField(max_length=20, null=True)
    # party and politics
    party = models.CharField(max_length=20)
    state = models.CharField(max_length=2)
    @property
    def full_name(self):
        "A senator's full name"
        return f"{self.first_name} {self.middle_name} {self.last_name} {self.suffix}"
    
    
