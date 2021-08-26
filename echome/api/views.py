from django.http.response import JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render

def index(request):
    return JsonResponse({"type": "index-one"})


def indextwo(request):
    return JsonResponse({"type": "index-two"})