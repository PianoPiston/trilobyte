import os

import uvicorn


uvicorn.run("server.app:create_app", factory=True, host=os.environ.get("DRIFTCI_HOST", "127.0.0.1"), port=int(os.environ.get("DRIFTCI_PORT", "8000")))
