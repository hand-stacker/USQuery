from django.db import models
from SenateQuery import models as SQmodels

# Create your models here.

# id : CCC_N_XXXX, CCC is congress, N is code for bill type, XXXX is bill number
class Bill(models.Model):
    id = models.IntegerField(primary_key=True)
    sponsor = models.ForeignKey(SQmodels.Membership, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    title = models.CharField(max_length=2000)
    origin_date = models.DateField()
    latest_action  = models.DateField()
    def getStatus(self):
        if self.status : return "Became Public Law"
        return "Still Just A Bill"
    
    def getOrigin(self):
        n = (self.id // 10000) % 10
        return "Senate" if n <4 else "House" 
    
    def getOriginCode(self):  
        n = (self.id // 10000) % 10
        return "S" if (n < 4) else "H"    
    
    def getType(self):
        n = (self.id // 10000) % 10
        types = {
            0 : "S",
            1 : "S.RES",
            2 : "S.J.RES",
            3 : "S.CON.RES",
            4 : "HR",
            5 : "H.RES",
            6 : "H.J.RES",
            7 : "H.CON.RES"}
        return types[n]
    
    def getTypeURL(self):
        n = (self.id // 10000) % 10
        types = {
            0 : "s",
            1 : "sres",
            2 : "sjres",
            3 : "sconres",
            4 : "hr",
            5 : "hres",
            6 : "hjres",
            7 : "hconres"}
        return types[n]
    
    def getNum(self):
        return self.id % 10000
    
    def getNumStr(self):
        return str(self.id % 10000)
    
    def getCongress(self):
        return self.id // 100000
    
    def getURL(self):
        return str(self.getCongress()) + "/" + self.getTypeURL()
    
    def __str__(self):
        return self.getType() + " " + self.getNumStr()
    
    class Meta():
        ordering = ["-origin_date", "-latest_action", "-id"]
                
        
        

# id : CCC_H_S_XXXXX , CCC is congress, H is 0 if senate, else house, S is session 1 or 2, XXXXX is vote num
class Vote(models.Model):
    id = models.IntegerField(primary_key=True)
    congress = models.ForeignKey(SQmodels.Congress, on_delete=models.CASCADE)
    house = models.BooleanField(default=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, blank = True)
    dateTime = models.DateTimeField()
    question = models.CharField(max_length=100)
    title = models.CharField(max_length=500, blank=True)
    result = models.CharField(max_length=42)
    
    yeas = models.ManyToManyField(SQmodels.Membership, related_name='yeas', blank = True)
    nays = models.ManyToManyField(SQmodels.Membership, related_name='nays', blank = True)
    pres = models.ManyToManyField(SQmodels.Membership, related_name='pres', blank = True)
    novt = models.ManyToManyField(SQmodels.Membership, related_name='novt', blank = True)
    def inHouse(self):
        return (self.id // 1000000) % 10 == 1
    def __str__(self):
        return "congress " + self.congress.__str__() + " : Time "  + str(self.dateTime) + " : " + self.bill.__str__() + " " + self.question
    class Meta():
        ordering = ["-dateTime"]
    
class ChoiceVote(models.Model) :
    id = models.IntegerField(primary_key=True)
    congress = models.ForeignKey(SQmodels.Congress, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, blank = True)
    dateTime = models.DateTimeField()
    question = models.CharField(max_length=40)
    title = models.CharField(max_length=500, blank=True)
    result = models.CharField(max_length=40)
    def __str__(self):
        return "congress " +  self.congress.__str__() + " : " + self.bill.getStr() + " " + self.question
    class Meta():
        ordering = ["-dateTime"]

class Choice(models.Model) :
   id = models.BigAutoField(primary_key=True)
   choice_vote = models.ForeignKey(ChoiceVote, on_delete=models.CASCADE)
   choice = models.CharField(max_length=40)
   supporters = models.ManyToManyField(SQmodels.Membership)
   def __str__(self):
        return self.choice + "->" + self.choice_vote.__str__()
   