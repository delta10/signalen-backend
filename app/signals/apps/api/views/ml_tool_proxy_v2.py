import pickle

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from signals.apps.classification.models import Classifier


@extend_schema(exclude=True)
class LegacyMlPredictCategoryViewV2(APIView):
    def post(self, request, *args, **kwargs):
        try:
            classifier = Classifier.objects.get(is_active=True)

            main_model = pickle.load(classifier.main_model)
            sub_model = pickle.load(classifier.sub_model)

            data = {'hoofdrubriek': [main_model.predict([request.data['text']])], 'subrubriek': [sub_model.predict([request.data['text']])]}
        except Classifier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(status=status.HTTP_200_OK, data=data)


