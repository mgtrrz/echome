import logging
from django.http.request import QueryDict
from rest_framework import status
from rest_framework.response import Response
from django.http import HttpRequest

logger = logging.getLogger(__name__)

class HelperView():

    def require_parameters(self, request: HttpRequest, required: list):
        """
        Check the request POST data for each provided item in `required`.
        If there are some items missing, add it to the class' `missing_parameters`
        variable and return the `missing_parameters` list which may be True (if it
        contains items) or False (if empty)
        """
        logger.debug("View supplied required parameters:")
        logger.debug(required)
        logger.debug(request.POST)
        missing_params = []
        for req in required:
            if req not in request.POST:
                missing_params.append(req)
        
        return missing_params
    

    def missing_parameter_response(self, params:list) -> Response:
        """
        Return a rest_framework response with a list of the missing parameters
        """
        return Response({
            'success': False,
            'details': "Missing the following required parameters",
            "parameters": params
        }, status=status.HTTP_400_BAD_REQUEST)
    

    def error_response(self, message:str, status:status) -> Response:
        msg = {
            'success': False,
            'details': message
        }
        return Response(msg, status=status)


    def internal_server_error_response(self)  -> Response:
        return Response({
            'success': False,
            'details': 'Internal Server Error. See logs for details.'
        }, status.HTTP_500_INTERNAL_SERVER_ERROR)


    def not_found_response(self, message:str = None) -> Response:
        return Response({
            'success': False,
            'details': message if message is not None else "Resource does not exist",
        }, status=status.HTTP_404_NOT_FOUND)


    def success_response(self, extra_info:dict = {}, message:str = None) -> Response:
        msg = {
            'success': True,
            'details': message if message is not None else "",
        }
        if extra_info:
            msg['results'] = extra_info

        return Response(msg, status=status.HTTP_200_OK)


    def unpack_tags(self, request:HttpRequest=None):
        logger.debug("Unpacking tags")
        """
        Convert parameter tags (e.g. Tag.1.Key=Name, Tag.1.Value=MyVm, Tag.2.Key=Env, etc.)
        to a dictionary e.g. {"Name": "MyVm", "Env": "stage"}
        """
        dict_tags = {}
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
            x += 1
        
        logger.debug(dict_tags)
        return dict_tags
    
    
    def unpack_comma_separated_list(self, key:str, request:QueryDict):
        logger.debug("Unpacking comma separated list")
        items = str.split(request.get(key), ",")
        logger.debug(items)
        return items
