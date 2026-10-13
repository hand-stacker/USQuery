"""Bill vote-prediction pipeline (feature extraction + trained model).

The implementation and model weights are not included in this public
snapshot. These stubs keep the same interface: the prediction endpoints, tier
gating and credit metering in BillQuery/views.py are public and tested; with
these stubs every bill reports that no prediction is available.
"""

import datetime


class PredictionDataError(Exception):
    def __init__(self, reason, detail):
        self.reason = reason
        self.detail = detail
        super().__init__(detail)


def current_congress():
    return (datetime.date.today().year - 1787) // 2


def createPredictions(bill_id):
    return -1


def getPredictionBatch(bill_id, in_house, sample_size, run_sample=True):
    return None


def deletePred(bill_id):
    return None
