from sys import maxsize
from turtle import mode
from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API

class Senator(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    full_name = models.CharField(max_length=40)
    image_link = models.CharField(max_length=150, null = True, blank = True)
    url = models.CharField(max_length=200, null = True, blank = True)
    twitter = models.CharField(max_length=40, null = True, blank = True)
    facebook = models.CharField(max_length=40, null = True, blank = True)
    youtube = models.CharField(max_length=40, null = True, blank = True)
    office = models.CharField(max_length=100, null = True, blank = True)
    phone = models.CharField(max_length=12, null = True, blank = True)
    votesmart_id = models.CharField(max_length=6, null = True, blank = True)
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
    party = models.CharField(max_length=30)
    short_title = models.CharField(max_length=4)
    long_title = models.CharField(max_length=40) 
    start_date = models.CharField(max_length=10)
    end_date = models.CharField(max_length=10)
    total_votes = models.IntegerField(null = True, blank = True)
    missed_votes = models.IntegerField(null = True, blank = True)
    total_present = models.IntegerField(null = True, blank = True)
    party_votes_pct = models.FloatField(null = True, blank = True)
    nonparty_votes_pct = models.FloatField(null = True, blank = True)
    missed_votes_pct = models.FloatField(null = True, blank = True)
    cook_pvi = models.CharField(max_length=4, null = True, blank = True)
    def __str__(self):
        return "Congress :"  + self.congress + " State:" + self.state + " Senator:" + self.senator
