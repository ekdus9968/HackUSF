import json
import sys
from auth import run_auth

user = run_auth()
if user:
    print(json.dumps(user), flush=True)