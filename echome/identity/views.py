import logging
from rest_framework import status
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
            "Action",
        ]
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)

        requested_action = request.POST["Action"].lower()

        if requested_action == "user-access-key":
            try:
                details = self.create_access_key(request)
            except User.DoesNotExist:
                return self.error_response(
                    "User specified does not exist.",
                    status.HTTP_400_BAD_REQUEST
                )
            except Exception:
                return self.internal_server_error_response()
            
            return self.success_response(details)
        elif requested_action == "user":
            pass
        else:
            return self.error_response(
                "Unknown action specified",
                status.HTTP_400_BAD_REQUEST
            )


    def create_access_key(self, request):
        if "UserName" in request.POST:
            try:
                user = User.objects.get(
                    username=request.POST["UserName"],
                    account=request.user.account,
                    type=User.Type.REGULAR
                )
            except User.DoesNotExist:
                raise
        else:
            user = request.user.get_top_level_user()

        new_key = User(
            type = User.Type.ACCESS_KEY,
            account = user.account,
            parent = user
        )
        new_key.generate_id()
        new_key.username = new_key.user_id
        key = new_key.generate_secret()
        try:
            new_key.save()
            return {
                "username": user.username,
                "access_id": new_key.username,
                "secret_key": key
            }
        except Exception as e:
            logger.exception(e)
            raise


class ModifyUser(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if missing_params := self.require_parameters(request, ["Action"]):
            return self.missing_parameter_response(missing_params)

        requested_action = request.POST["Action"].lower()

        if requested_action == "update-user-access-key":
            if missing_params := self.require_parameters(request, ["AccessKeyId", "Status"]):
                return self.missing_parameter_response(missing_params)

            new_status = request.POST["Status"].lower()
            if new_status == "active":
                    new_status = True
            elif new_status == "inactive":
                new_status = False
            else:
                return self.error_response(
                    "Unknown status provided.",
                    status.HTTP_400_BAD_REQUEST
                )

            try:
                self.enable_disable_access_key(request, is_active=new_status)
            except User.DoesNotExist:
                return self.error_response(
                    "Access Key ID specified does not exist.",
                    status.HTTP_400_BAD_REQUEST
                )

            return self.success_response()

        elif requested_action == "delete-user-access-key":
            if missing_params := self.require_parameters(request, ["AccessKeyId"]):
                return self.missing_parameter_response(missing_params)
    
            try:
                self.delete_access_key(request)
            except User.DoesNotExist:
                return self.error_response(
                    "Access Key ID specified does not exist.",
                    status.HTTP_400_BAD_REQUEST
                )
            
            return self.success_response()

        else:
            return self.error_response(
                "Unknown action specified",
                status.HTTP_400_BAD_REQUEST
            )


    def enable_disable_access_key(self, request, is_active:bool):
        """Enables or disables an access key"""
        try:
            access_key:User = User.objects.get(
                account=request.user.account,
                type=User.Type.ACCESS_KEY,
                username=request.POST["AccessKeyId"]
            )
        except User.DoesNotExist:
            raise

        access_key.is_active = is_active
        access_key.save()


    def delete_access_key(self, request):
        try:
            access_key:User = User.objects.get(
                account=request.user.account,
                type=User.Type.ACCESS_KEY,
                username=request.POST["AccessKeyId"]
            )
        except User.DoesNotExist:
            raise

        access_key.delete()

