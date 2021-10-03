import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from api.api_view import HelperView
from .models import User
from .serializer import UserSerializer, UserAccessKeySerializer

logger = logging.getLogger(__name__)

class DescribeUsers(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        i = []
        try:
            if user_id == "all":
                users = User.objects.filter(
                    account=request.user.account,
                    type=User.Type.REGULAR
                )

                for user in users:
                    i.append(UserSerializer(user).data)
            else:
                user = User.objects.get(
                    account=request.user.account,
                    type=User.Type.REGULAR,
                    username=user_id
                )

                user_dict = UserSerializer(user).data

                access_keys = User.objects.filter(
                    account=request.user.account,
                    type=User.Type.ACCESS_KEY,
                    parent_id=user
                )

                k = []
                for a_key in access_keys:
                    k.append(UserAccessKeySerializer(a_key).data)

                user_dict["access_keys"] = k
                i.append(user_dict)

        except User.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()

        return self.success_response(i)


class CreateUser(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "UserName",
        ]
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)

        new_user = User.manager
