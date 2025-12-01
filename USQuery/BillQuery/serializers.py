from rest_framework import serializers
from SenateQuery.serializers import MembershipSimpleModelSerializer
from .models import Bill, Vote

class BillModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = '__all__'

class VoteModelSerializer(serializers.ModelSerializer):
    yeas = MembershipSimpleModelSerializer(many=True, read_only=True)
    nays = MembershipSimpleModelSerializer(many=True, read_only=True)
    pres = MembershipSimpleModelSerializer(many=True, read_only=True)
    novt = MembershipSimpleModelSerializer(many=True, read_only=True)
    class Meta:
        model = Vote
        fields = ['id', 'congress', 'house', 'bill', 'dateTime', 'question', 'title', 'result', 'yeas', 'nays', 'pres', 'novt']

class VoteModelSerializerSimple(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'congress', 'house', 'bill', 'dateTime', 'question', 'title', 'result']