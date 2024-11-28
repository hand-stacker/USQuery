from sys import maxsize
from turtle import mode
from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API

class Member(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    full_name = models.CharField(max_length=40)
    image_link = models.CharField(max_length=150, null = True, blank = True)
    api_url = models.CharField(max_length=200, null = True, blank = True)
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
    members = models.ManyToManyField(Member, through="Membership", related_name="members_set")
    def __str__(self):
        return str(self.congress_num)
    
class Membership(models.Model):
    congress = models.ForeignKey(Congress, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    district_num = models.IntegerField(null = True, blank = True)
    chamber = models.CharField(max_length=25)
    state = models.CharField(max_length=2)
    party = models.CharField(max_length=30)
    start_date = models.CharField(max_length=10)
    end_date = models.CharField(max_length=10, null = True)
    def __str__(self):
        if self.chamber == "Senate":
            return "Congress :"  + self.congress + " State:" + self.state + " Senator:" + self.member
        else:
            return "Congress :"  + self.congress + " State:" + self.state + " Representative:" + self.member
'''    
class Senatorship(Membership):
    senator = models.ForeignKey(Member, on_delete=models.CASCADE)
    def __str__(self):
        return "Congress :"  + self.congress + " State:" + self.state + " Senator:" + self.senator

class Representativeship(Membership):
    representative = models.ForeignKey(Member, on_delete=models.CASCADE)
    district_num = 
    def __str__(self):
        return "Congress :"  + self.congress + " State:" + self.state + " Representative:" + self.representative 
'''
    

