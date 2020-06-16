import sys

class Response:
    @staticmethod
    def unexpected_response(msg=None, exit=False):
        print("\tUnexpected response from server.")
        if msg:
            print(f"\tAdditional information: {msg}")
        if exit:
            sys.exit(1)
    
    @staticmethod
    def unauthorized_response(msg=None, exit=False):
        print("\t401 Unauthorized")
        print("\tUnable to login or authorize with the ecHome server.")
        if msg:
            print(f"\tAdditional information: {msg}")
        if exit:
            sys.exit(1)