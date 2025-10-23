import os

os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("SETTINGS_SECRET_KEY", "contract-test-secret")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

import tests.contracts.test_schemathesis as mod
from schemathesis import openapi as schemathesis_openapi

schema = schemathesis_openapi.from_asgi("/openapi.json", mod.app)
operation = schema.get("/ai/digest/watchlists", "post")["post"]
case = operation.make_case()
print("initial query", case.query)
print("initial body", case.body)
