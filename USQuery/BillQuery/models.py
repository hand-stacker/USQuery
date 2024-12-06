from tkinter import CASCADE
from django.db import models
from SenateQuery import models as SQmodels

# Create your models here.
"""
class Bill(models.Model):
    id = models.CharField(primary_key=True, max_length=15)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    house = models.Choices("House", "Representative")
    votes_in_favor = models.ManyToManyField(SQmodels.Member)
    votes_against = models.ManyToManyField(SQmodels.Member)
"""

class Vote(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    congress = models.ForeignKey(SQmodels.Congress, on_delete=models.CASCADE)
    issue = models.CharField( max_length=10, blank=True, null=True)
    dateTime = models.DateTimeField()
    question = models.CharField(max_length=40)
    title = models.CharField(max_length=500, blank=True, null=True)
    result = models.CharField(max_length=20)
    
    yeas = models.ManyToManyField(SQmodels.Membership, related_name='yeas')
    nays = models.ManyToManyField(SQmodels.Membership, related_name='nays')
    pres = models.ManyToManyField(SQmodels.Membership, related_name='pres')
    novt = models.ManyToManyField(SQmodels.Membership, related_name='novt')
    def __str__(self):
        return "congress " + self.congress.__str__() + " : Time "  + str(self.dateTime) + " : " + self.issue + " " + self.question
    
class ChoiceVote(models.Model) :
    id = models.CharField(primary_key=True, max_length=10)
    congress = models.ForeignKey(SQmodels.Congress, on_delete=models.CASCADE)
    issue = models.CharField( max_length=10, blank=True, null=True)
    dateTime = models.DateTimeField()
    question = models.CharField(max_length=40)
    title = models.CharField(max_length=500, blank=True, null=True)
    result = models.CharField(max_length=40)
    def __str__(self):
        return "congress " +  self.congress.__str__() + " : " + self.issue + " " + self.question

class Choice(models.Model) :
   id = models.BigAutoField(primary_key=True)
   choice_vote = models.ForeignKey(ChoiceVote, on_delete=models.CASCADE)
   choice = models.CharField(max_length=40)
   supporters = models.ManyToManyField(SQmodels.Membership)
   def __str__(self):
        return self.choice + "->" + self.choice_vote.__str__()
   