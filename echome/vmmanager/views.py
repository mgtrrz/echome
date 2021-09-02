from django.shortcuts import render
from django.http.response import JsonResponse
from django.views import View


class CreateVM(View):
    def get(self, request):
        return JsonResponse({"got": True})

    def post(self, request):
        # <view logic>
        return JsonResponse({"put": True})