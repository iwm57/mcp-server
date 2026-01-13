import os
from dotenv import load_dotenv

load_dotenv()

ACTUAL_BRIDGE_URL = os.getenv(
    "ACTUAL_BRIDGE_URL",
    "http://actual-bridge:3000"
)

REQUEST_TIMEOUT = 15
