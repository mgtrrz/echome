from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.http import HttpRequest

class View(APIView):
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
                "message": "Missing the following required parameters",
                "parameters": self.missing_parameters
            }, status=status.HTTP_400_BAD_REQUEST)
    

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