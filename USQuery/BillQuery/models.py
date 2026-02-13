from django.db import models
from SenateQuery import models as SQmodels
from datetime import date
from django.db.models import Q

types = {
            's' : 0,
            'sres' : 1,
            'sjres' : 2,
            'sconres' : 3,
            'hr' : 4,
            'hres' : 5,
            'hjres' : 6,
            'hconres' : 7,
            '!S' : (0,3),
            '!H' : (4,7)}
## due to bad planning the bill ids can be of integer form CCC_T_XXXX or CCC_T_XXXXX
# (CCC is congress num, T is bill type, XXXX is bill num) if the bill number is higher than 9999
class TypeManager(models.Manager):
    def get_from_type(self, _type, start_date, end_date):
        if _type == '!' or _type == '':
            return super(TypeManager, self).get_queryset().filter(latest_action__gte=start_date, latest_action__lte=end_date) 
        if _type == '!S' or _type == '!H':
            _addr_bgn = 10000 * types[_type][0]
            _addr_end = 10000 * types[_type][1]
        else:
            _addr_bgn = 10000 * types[_type]
            _addr_end = 10000 * types[_type]
        query = Q(id__gte = 118_0_00001 + (_addr_bgn * 10),id__lte = 118_0_99999 + (_addr_end * 10))
        _start = 110_0_0001
        _end = 110_0_9999
        query.add(Q(id__gte = _start + _addr_bgn,id__lte = _end + _addr_end), Q.OR)
        for i in range(1,11):
            _start += 1_0_0000
            _end += 1_0_0000
            query.add(Q(id__gte = _start + _addr_bgn,id__lte = _end + _addr_end), Q.OR)
        query.add(Q(latest_action__gte=start_date, latest_action__lte=end_date), Q.AND)
        return super(TypeManager, self).get_queryset().filter(query)

# CCC_H_S_XXXXX
class TypeManagerVote(models.Manager):
    def get_from_type(self, _type, start_date, end_date):
        if _type == '!':
            return super(TypeManagerVote, self).get_queryset().filter(dateTime__gte=start_date, dateTime__lte=end_date) 
        _addr = 1_0_00000 if _type == 'h' else 0
        _start = 110_0_1_00001
        _end = 110_0_2_99999
        query = Q(id__gte = _start + _addr,id__lte = _end + _addr)
        for i in range(1,11):
            _start += 1_0_0_00000
            _end += 1_0_0_00000
            query.add(Q(id__gte = _start + _addr,id__lte = _end + _addr), Q.OR)
        query.add(Q(dateTime__gte=start_date, dateTime__lte=end_date), Q.AND)
        return super(TypeManagerVote, self).get_queryset().filter(query)

class Subject(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    subtype = models.IntegerField(default=0)
    def getSubtype(self):
        subtypes = ["Subject", "Geographic Entity", "Organization"]
        return subtypes[self.subtype]
    def __str__(self):
        return self.name
    class Meta():
        ordering = ["name"]

# id : CCC_N_XXXX, CCC is congress, N is code for bill type, XXXX is bill number
class Bill(models.Model):
    id = models.IntegerField(primary_key=True)
    sponsor = models.ForeignKey(SQmodels.Membership, on_delete=models.CASCADE)
    cosponsors = models.ManyToManyField(SQmodels.Membership, related_name='cosponsor_set')
    policy_area = models.CharField(max_length=50, null=True, blank=True)
    subjects = models.ManyToManyField(Subject)
    related_bills = models.ManyToManyField('self', symmetrical=False)
    status = models.BooleanField(default=False)
    title = models.CharField(max_length=2000)
    origin_date = models.DateField(db_index=True)
    latest_action = models.DateField(db_index=True)
    latest_db_update = models.DateField(null=True, blank = True)
    objects = models.Manager()
    type_objects =TypeManager()

    def getStatus(self):
        if self.status : return "Became Public Law"
        return "Still Just A Bill"
    
    def getOrigin(self):
        if (self.id >= 100000000) : n = (self.id // 100000) % 10
        else : n = (self.id // 10000) % 10
        return "Senate" if n <4 else "House" 
    
    def getOriginCode(self):  
        if (self.id >= 100000000) : n = (self.id // 100000) % 10
        else : n = (self.id // 10000) % 10
        return "S" if (n < 4) else "H"    
    
    def getType(self):
        if (self.id >= 100000000) : n = (self.id // 100000) % 10
        else : n = (self.id // 10000) % 10
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
        if (self.id >= 100000000) : n = (self.id // 100000) % 10
        else : n = (self.id // 10000) % 10
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
        if (self.id >= 100000000) : return self.id % 100000
        return self.id % 10000
    
    def getNumStr(self):
        if (self.id >= 100000000) : return str(self.id % 100000)
        return str(self.id % 10000)
    
    def getCongress(self):
        if (self.id >= 100000000) : return self.id // 1000000
        return self.id // 100000
    
    def getURL(self):
        return str(self.getCongress()) + "/" + self.getTypeURL() + "/" + self.getNumStr()
    
    def __str__(self):
        return self.getType() + " " + self.getNumStr()
    
    class Meta():
        ordering = ["-latest_action", "origin_date", "-id"]
                
# id : CCC_H_S_XXXXX , CCC is congress, H is 0 if senate, else house, S is session 1 or 2, XXXXX is vote num
class Vote(models.Model):
    id = models.IntegerField(primary_key=True)
    congress = models.ForeignKey(SQmodels.Congress, on_delete=models.CASCADE)
    house = models.BooleanField(default=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, blank = True, null = True)
    dateTime = models.DateTimeField()
    question = models.CharField(max_length=100)
    title = models.CharField(max_length=500, blank=True, null=True)
    result = models.CharField(max_length=50)
    
    yeas = models.ManyToManyField(SQmodels.Membership, related_name='yeas', blank = True)
    nays = models.ManyToManyField(SQmodels.Membership, related_name='nays', blank = True)
    pres = models.ManyToManyField(SQmodels.Membership, related_name='pres', blank = True)
    novt = models.ManyToManyField(SQmodels.Membership, related_name='novt', blank = True)

    objects = models.Manager()
    type_objects =TypeManagerVote()

    def getDate(self):
        return self.dateTime.strftime("%Y-%m-%d")
    def inHouse(self):
        return (self.id // 1000000) % 10 == 1
    def __str__(self):
        return "congress " + self.congress.__str__() + " : Date "  + self.getDate() + " : " + self.bill.__str__() + " " + self.question
    class Meta():
        ordering = ["-dateTime", "-id"]
    
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

## same key as Bill object, should hold AI generated summary
class BillSummary(models.Model): 
    id = models.IntegerField(primary_key=True)
    source_date = models.DateField(default=date(1,1,1))
    summary = models.TextField(default="We cannot provide a summary at this time.")
    def __str__(self):
        return str(self.id)

class BillPrediction(models.Model):
    id = models.IntegerField(primary_key=True)
    creation_date = models.DateField()

class BinaryProbability(models.Model):
    id = models.BigAutoField(primary_key=True)
    bill_pred = models.ForeignKey(BillPrediction, on_delete=models.CASCADE)
    state = models.CharField(max_length=2)
    in_house = models.BooleanField(default=True)
    party = models.CharField(max_length=30)
    counts = models.IntegerField()
    p = models.DecimalField(max_digits=5, decimal_places=5)

