import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from .serializers import GuestImageSerializer, UserImageSerializer
from .models import GuestImage, UserImage

# Combine guest and user image and just use image_type as an enum to differentiat
# there's no need to have two separate DBs
# Could also argue that images can go under the VM namespace

logger = logging.getLogger(__name__)

# Create your views here.
class CreateImage(HelperView, APIView):
    pass


class DeleteImage(HelperView, APIView):
    pass  


class DescribeImage(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, type:str, image_id:str):
        i = []

        if type not in ["guest", "user"]:
            return self.error_response(
                "Unknown type",
                status = status.HTTP_404_NOT_FOUND
            )
        
        if type == "guest":
            try:
                if image_id == "all":
                    images = GuestImage.objects.all()
                else:
                    images = []
                    images.append(GuestImage.objects.get(
                        image_id=image_id
                    ))
                
                for image in images:
                    i.append(GuestImageSerializer(image).data)
            except GuestImage.DoesNotExist as e:
                logger.debug(e)
                return self.not_found_response()
            except Exception as e:
                logger.exception(e)
                return self.internal_server_error_response()

        return self.success_response(i)


class ModifyImage(HelperView, APIView):
    pass
