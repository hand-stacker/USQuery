from rest_framework import serializers
from SenateQuery.serializers import MembershipSimpleModelSerializer
from .models import Bill, Vote, US_EASTERN

class BillModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = '__all__'

class VoteModelSerializer(serializers.ModelSerializer):
    # Same instant, rendered with the Eastern offset (e.g. ...T21:30:00-04:00) so
    # the date part is the day the vote happened in Washington.
    dateTime = serializers.DateTimeField(default_timezone=US_EASTERN, read_only=True)
    yeas = MembershipSimpleModelSerializer(many=True, read_only=True)
    nays = MembershipSimpleModelSerializer(many=True, read_only=True)
    pres = MembershipSimpleModelSerializer(many=True, read_only=True)
    novt = MembershipSimpleModelSerializer(many=True, read_only=True)
    class Meta:
        model = Vote
        fields = ['id', 'congress', 'house', 'bill', 'dateTime', 'question', 'title', 'result', 'yeas', 'nays', 'pres', 'novt']

class VoteModelSerializerSimple(serializers.ModelSerializer):
    dateTime = serializers.DateTimeField(default_timezone=US_EASTERN, read_only=True)
    class Meta:
        model = Vote
        fields = ['id', 'congress', 'house', 'bill', 'dateTime', 'question', 'title', 'result']