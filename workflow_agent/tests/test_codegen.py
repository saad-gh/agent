from django.test import TransactionTestCase
from workflow_agent.models import JinjaHelper, GeneratedFunction
from workflow_agent.sanitize import validate_source
from workflow_agent.helpers import load_approved_helpers
from workflow_agent.run_safe import run_generated_function


class CodegenSanitizeAndRunTest(TransactionTestCase):
    def test_sanitize_valid_source(self):
        source = """
import json
import re

def clean_data(val):
    s = re.sub(r'[^a-zA-Z0-9]', '', str(val))
    return {"cleaned": s}
"""
        is_valid, err = validate_source(source)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_sanitize_forbidden_imports(self):
        bad_source_os = "import os; os.system('echo hack')"
        is_valid_os, err_os = validate_source(bad_source_os)
        self.assertFalse(is_valid_os)
        self.assertIn("Forbidden import", err_os)

        bad_source_sub = "import subprocess; subprocess.run(['ls'])"
        is_valid_sub, err_sub = validate_source(bad_source_sub)
        self.assertFalse(is_valid_sub)
        self.assertIn("Forbidden import", err_sub)

    def test_sanitize_forbidden_calls(self):
        bad_source = "def run(): eval('1 + 1')"
        is_valid, err = validate_source(bad_source)
        self.assertFalse(is_valid)
        self.assertIn("Forbidden", err)

    def test_load_approved_jinja_helpers(self):
        # 1. Create unapproved helper
        JinjaHelper.objects.create(
            name="unapproved_fmt",
            source="def unapproved_fmt(): return 'bad'",
            source_hash="hash-1",
            is_approved=False
        )

        # 2. Create approved helper
        JinjaHelper.objects.create(
            name="approved_fmt",
            source="def approved_fmt(val):\n    return f'FMT_{val}'",
            source_hash="hash-2",
            is_approved=True
        )

        helpers = load_approved_helpers()
        self.assertIn("approved_fmt", helpers)
        self.assertNotIn("unapproved_fmt", helpers)
        self.assertEqual(helpers["approved_fmt"]("123"), "FMT_123")

    def test_run_approved_generated_function(self):
        # 1. Unapproved function should be rejected
        GeneratedFunction.objects.create(
            slug="unapproved-fn",
            source="def unapproved_fn(kwargs):\n    return {'val': 1}",
            source_hash="ghash-1",
            is_approved=False
        )
        res_un = run_generated_function("unapproved-fn")
        self.assertEqual(res_un["status"], "error")
        self.assertIn("not approved", res_un["error"])

        # 2. Approved function executes in subprocess
        GeneratedFunction.objects.create(
            slug="approved-fn",
            source="def approved_fn(kwargs):\n    num = kwargs.get('x', 0)\n    return {'result': num * 2}",
            source_hash="ghash-2",
            is_approved=True
        )
        res_app = run_generated_function("approved-fn", kwargs={"x": 21})
        self.assertEqual(res_app["status"], "success")
        self.assertEqual(res_app["result"], 42)

    def test_run_generated_function_timeout(self):
        # Infinite loop function should hit timeout
        GeneratedFunction.objects.create(
            slug="slow-loop-fn",
            source="def slow_loop_fn(kwargs):\n    while True:\n        pass",
            source_hash="ghash-3",
            is_approved=True
        )
        res_slow = run_generated_function("slow-loop-fn", timeout=1)
        self.assertEqual(res_slow["status"], "error")
        self.assertIn("timed out", res_slow["error"])
