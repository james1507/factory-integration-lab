"""Runtime settings, read once from the environment at import."""
import os

MES_SECRET = os.environ.get("MES_WEBHOOK_SECRET", "dev-mes-secret").encode()
ERP_SECRET = os.environ.get("ERP_WEBHOOK_SECRET", "dev-erp-secret").encode()

# Allowed age of a signed request, in seconds.
TOLERANCE_S = int(os.environ.get("WEBHOOK_TOLERANCE_S", "300"))

MAX_BODY_BYTES = 1 << 20
