from django.http.response import JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

def index(request):
    return JsonResponse({"type": "index-one"})


def indextwo(request):
    if IsAuthenticated:
        return JsonResponse({"type": "index-two"})
    else:
        return JsonResponse({"error": "Not-logged-in"})