from rest_framework import status
from rest_framework.response import Response
from django.http import HttpRequest

class HelperView():
    missing_parameters: list = list()

    def require_parameters(self, request: HttpRequest, required: list):
        """
        Check the request POST data for each provided item in `required`.
        If there are some items missing, add it to the class' `missing_parameters`
        variable and return the `missing_parameters` list which may be True (if it
        contains items) or False (if empty)
        """
        for req in required:
            if req not in request.POST:
                self.missing_parameters.append(req)
        
        return self.missing_parameters
    
    def missing_parameter_response(self):
        """
        Return a rest_framework response with a list of the missing parameters
        """
        return Response({
            'success': False,
            'details': "Missing the following required parameters",
            "parameters": self.missing_parameters
        }, status=status.HTTP_400_BAD_REQUEST)
    

    def error_response(self, message:str, status:status):
        msg = {
            'success': False,
            'details': message
        }
        return Response(msg, status=status)


    def not_found_response(self, message:str = None):
        return Response({
            'success': False,
            'details': message if not None else "Resources does not exist.",
        }, status=status.HTTP_404_NOT_FOUND)

    def success_response(self, extra_info:dict = {}, message:str = None):
        msg = {
            'success': True,
            'details': message if not None else "",
        }
        if extra_info:
            msg['results'] = extra_info

        Response(msg, status=status.HTTP_200_OK)

    def unpack_tags(self, request: HttpRequest=None):
        """
        Convert parameter tags (e.g. Tag.1.Key=Name, Tag.1.Value=MyVm, Tag.2.Key=Env, etc.)
        to a dictionary e.g. {"Name": "MyVm", "Env": "stage"}
        """
        dict_tags = dict()
        there_are_tags = True
        x = 1
        while there_are_tags:
            if f"Tag.{x}.Key" in request.POST:
                keyname = request.POST[f"Tag.{x}.Key"]
                if f"Tag.{x}.Value" in request.POST:
                    value = request.POST[f"Tag.{x}.Value"]
                else:
                    value = ""

                dict_tags[keyname] = value
            else:
                there_are_tags = False
                continue
            x = x + 1
        
        return dict_tags