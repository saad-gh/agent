import os
import tempfile
from django.test import TransactionTestCase
from workflow_orchestrator.models import Service
from workflow_agent.agent_core.storage import get_storage, LocalSpecStorage, GcsSpecStorage, S3SpecStorage
from workflow_agent.agent_core.spec import validate_api_spec, save_spec_for_service, load_spec_for_service


class SpecStorageFoundationTest(TransactionTestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.service = Service.objects.create(name="test_service")

    def test_storage_factory_routing(self):
        local_st = get_storage("specs/shopify.yaml")
        self.assertIsInstance(local_st, LocalSpecStorage)

        gcs_st = get_storage("gs://my-bucket/specs/shopify.yaml")
        self.assertIsInstance(gcs_st, GcsSpecStorage)

        s3_st = get_storage("s3://my-bucket/specs/shopify.yaml")
        self.assertIsInstance(s3_st, S3SpecStorage)

    def test_local_storage_read_write(self):
        storage = LocalSpecStorage(base_dir=self.tmp_dir)
        test_path = "test_spec.yaml"
        content = "service: shopify\nversion: '2024-01'\nendpoints: []"

        storage.write(test_path, content)
        self.assertTrue(storage.exists(test_path))

        read_content = storage.read(test_path)
        self.assertEqual(read_content, content)

    def test_validate_api_spec_valid_and_invalid(self):
        valid_spec = {
            "service": "shopify",
            "version": "2024-01",
            "endpoints": [
                {"slug": "list_orders", "method": "GET", "path": "/admin/api/2024-01/orders.json"}
            ]
        }
        is_valid, err = validate_api_spec(valid_spec)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        invalid_spec = {"service": "shopify"}  # missing version and endpoints
        is_valid_inv, err_inv = validate_api_spec(invalid_spec)
        self.assertFalse(is_valid_inv)
        self.assertIn("version", err_inv)

    def test_service_save_and_load_spec(self):
        spec_data = {
            "service": "test_service",
            "version": "v1",
            "endpoints": [
                {"slug": "get_items", "method": "GET", "path": "/api/v1/items"}
            ]
        }
        storage_path = os.path.join(self.tmp_dir, "test_service_v1.json")
        saved_path = save_spec_for_service(self.service, spec_data, path=storage_path, fmt="json")
        self.assertEqual(saved_path, storage_path)

        self.service.refresh_from_db()
        self.assertEqual(self.service.api_spec_path, storage_path)

        loaded_spec = load_spec_for_service(self.service)
        self.assertEqual(loaded_spec["service"], "test_service")
        self.assertEqual(len(loaded_spec["endpoints"]), 1)
