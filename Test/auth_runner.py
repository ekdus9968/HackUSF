import json
import sys
from auth import run_auth

user = run_auth()
if user:
    # Only JSON goes to stdout — everything else must go to stderr
    print(json.dumps(user), file=sys.stdout, flush=True)