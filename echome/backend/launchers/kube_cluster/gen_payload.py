#!/usr/bin/python
import sys
import json

with open("payload.json", "w") as fhandler:
    with open(sys.argv[1], "r") as reader:
        data = {
            "data": {
                "admin.conf": reader.read()
            }
        }
        fhandler.write(json.dumps(data, indent=4))