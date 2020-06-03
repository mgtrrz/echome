# import sys
# import requests
# from .session import Session
# from .vm import vm

# def resource(type, session: Session):
#     req_resource = getattr(sys.modules[__name__], type)
#     return req_resource(session)