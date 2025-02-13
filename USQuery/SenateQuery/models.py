from django.db import models

# Create your models here.
# This class is mostly for filtering and for html forms, more useful info is collected from the ProPublica API

class Member(models.Model):
    id = models.CharField(max_length=7, primary_key=True)
    full_name = models.CharField(max_length=40)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    image_link = models.CharField(max_length=150, null = True, blank = True)
    official_link = models.CharField(max_length=200, null = True, blank = True)
    twitter = models.CharField(max_length=40, null = True, blank = True)
    facebook = models.CharField(max_length=40, null = True, blank = True)
    youtube = models.CharField(max_length=40, null = True, blank = True)
    office = models.CharField(max_length=100, null = True, blank = True)
    phone = models.CharField(max_length=12, null = True, blank = True)
    birth_year = models.CharField(max_length=4, null = True, blank = True)
    death_year = models.CharField(max_length=4, null = True, blank = True)
    def __str__(self):
        return self.full_name
    def getAPIURL(self):
        return "https://api.congress.gov/v3/member/" + self.id
    class Meta():
        ordering = ["full_name"]
      
class Congress(models.Model):
    congress_num = models.IntegerField(primary_key=True)
    members = models.ManyToManyField(Member, through="Membership", related_name="members_set")
    start_year = models.IntegerField(null=True)
    end_year = models.IntegerField(null=True)
    def __str__(self):
        return str(self.congress_num)
    class Meta():
        ordering = ["-congress_num"]
    
class Membership(models.Model):
    id = models.BigAutoField(primary_key=True)
    congress = models.ForeignKey(Congress, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    district_num = models.IntegerField(null = True, blank = True)
    house = models.BooleanField(default = True)
    state = models.CharField(max_length=2)
    geoid = models.CharField(max_length=4)
    party = models.CharField(max_length=30)
    start_date = models.CharField(max_length=10)
    end_date = models.CharField(max_length=10, null = True)
    def getChamber(self):
        if self.house: return "House of Representatives"
        return "Senate"
    def __str__(self):
        if self.house:
            return "Congress :"  + self.congress.__str__() + " State: " + self.state + " Representative: " + self.member.__str__()
        else:
            return "Congress :"  + self.congress.__str__() + " State: " + self.state + " Senator: " + self.member.__str__()
    class Meta():
        ordering = ["state", "member__full_name"]
    

