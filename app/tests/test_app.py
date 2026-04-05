"""
Tests para flask-otel-demo
Ejecutar: python -m unittest tests.test_app -v
          python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest
import tempfile

os.environ.setdefault("OTEL_SERVICE_NAME", "flask-otel-test")
os.environ.setdefault("ENVIRONMENT", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_client(db_path):
    os.environ["DB_PATH"] = db_path
    import importlib
    import app as app_module
    importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), app_module


def _post(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


class TestHealth(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.client, _ = _make_client(self._tmp.name)
    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_index(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertEqual(body["service"], "flask-otel-test")
        self.assertIn("endpoints", body)

    def test_liveness(self):
        r = self.client.get("/health/live")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)["status"], "alive")

    def test_readiness(self):
        r = self.client.get("/health/ready")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)["status"], "ready")

    def test_metrics(self):
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"items_total", r.data)
        self.assertIn(b"app_info", r.data)


class TestItems(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.client, _ = _make_client(self._tmp.name)
    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_list_empty(self):
        r = self.client.get("/api/items")
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total"], 0)

    def test_create_success(self):
        r = _post(self.client, "/api/items", {"name": "Test", "description": "Desc"})
        self.assertEqual(r.status_code, 201)
        body = json.loads(r.data)
        self.assertEqual(body["name"], "Test")
        self.assertEqual(body["active"], 1)
        self.assertIn("id", body)

    def test_create_missing_name(self):
        r = _post(self.client, "/api/items", {"description": "sin nombre"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", json.loads(r.data))

    def test_create_empty_body(self):
        r = self.client.post("/api/items", data="", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_list_after_create(self):
        _post(self.client, "/api/items", {"name": "A"})
        _post(self.client, "/api/items", {"name": "B"})
        body = json.loads(self.client.get("/api/items").data)
        self.assertEqual(body["total"], 2)
        names = [i["name"] for i in body["items"]]
        self.assertIn("A", names)
        self.assertIn("B", names)

    def test_get_item(self):
        created = json.loads(_post(self.client, "/api/items", {"name": "GetMe"}).data)
        r = self.client.get(f"/api/items/{created['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)["name"], "GetMe")

    def test_get_not_found(self):
        r = self.client.get("/api/items/9999")
        self.assertEqual(r.status_code, 404)

    def test_delete(self):
        created = json.loads(_post(self.client, "/api/items", {"name": "Del"}).data)
        self.assertEqual(self.client.delete(f"/api/items/{created['id']}").status_code, 200)
        self.assertEqual(json.loads(self.client.get("/api/items").data)["total"], 0)

    def test_delete_not_found(self):
        self.assertEqual(self.client.delete("/api/items/9999").status_code, 404)


class TestProcess(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.client, _ = _make_client(self._tmp.name)
    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_process_default(self):
        r = _post(self.client, "/api/process", {})
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertIn("total", body)
        self.assertIn("results", body)

    def test_process_zero_errors(self):
        r = _post(self.client, "/api/process",
                  {"items": [{"id": 1}, {"id": 2}], "error_rate": 0.0})
        body = json.loads(r.data)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["errors"], 0)

    def test_process_all_errors(self):
        r = _post(self.client, "/api/process",
                  {"items": [{"id": 1}, {"id": 2}], "error_rate": 1.0})
        body = json.loads(r.data)
        self.assertEqual(body["errors"], 2)
        self.assertEqual(body["ok"], 0)

    def test_process_empty(self):
        r = _post(self.client, "/api/process", {"items": [], "error_rate": 0.0})
        body = json.loads(r.data)
        self.assertEqual(body["total"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
