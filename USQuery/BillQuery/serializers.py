from rest_framework import serializers
from .models import Bill, Vote, BillSummary, BillPrediction

class BillModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = '__all__'

class VoteModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = '__all__'

class VoteModelSerializerSimple(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'congress', 'house', 'bill', 'dateTime', 'question', 'title', 'result']
class BillSummaryModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillSummary
        fields = '__all__'

class BillPredictionModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillPrediction
        fields = '__all__'