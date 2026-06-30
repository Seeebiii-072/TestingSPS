import importlib.util
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db  # noqa: E402

ATTACHMENTS_ROUTE_PATH = Path(__file__).resolve().parents[1] / "routes" / "attachments.py"
attachments_spec = importlib.util.spec_from_file_location("attachments_route_under_test", ATTACHMENTS_ROUTE_PATH)
assert attachments_spec and attachments_spec.loader
attachments_module = importlib.util.module_from_spec(attachments_spec)
attachments_spec.loader.exec_module(attachments_module)


async def override_get_db():
    yield None


def test_anonymous_attachment_upload_is_rejected():
    app = FastAPI()
    app.include_router(attachments_module.router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        response = client.post(
            "/tickets/11111111-1111-1111-1111-111111111111/attachments",
            files={"file": ("proof.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 401
