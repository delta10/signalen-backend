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

            text = request.data['text']

            # Get prediction and probability for the main model
            main_prediction = main_model.predict([text])
            main_probability = main_model.predict_proba([text])

            # Get prediction and probability for the sub model
            sub_prediction = sub_model.predict([text])
            sub_probability = sub_model.predict_proba([text])

            data = {
                'hoofdrubriek': [
                    [main_prediction[0]],
                    [main_probability[0][0]]
                ],
                'subrubriek': [
                    [sub_prediction[0]],
                    [sub_probability[0][0]]
                ]
            }
        except Classifier.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(status=status.HTTP_200_OK, data=data)


