"""Offline installed SDK demo probe. To serve: soma-explorer --port 8000.

From a frontend checkout: npm --prefix apps/explorer ci, then
npm --prefix apps/explorer run dev; open http://127.0.0.1:5173 and choose demo.
No frontend binaries or datasets are bundled into the Python wheel.
"""

import json

from soma.sdk.explorer import create_app


def run():
    from fastapi.testclient import TestClient

    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get("/api/catalog")
        assert response.status_code == 200
        assert client.get("/api/experiments").status_code == 200
        assert "/Users/" not in response.text
        return {"status": response.status_code, "demo_available": True, "local_only": True}


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
