# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Process-level failure behavior for the STDIO entry point."""

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from analytics_mcp import server


class TestServerEntryPoint(unittest.TestCase):
    def test_fatal_error_is_sanitized_and_exits_nonzero(self):
        async def fail_with_sensitive_detail():
            raise RuntimeError(r"C:\sensitive\account-name.json")

        stderr = io.StringIO()
        with (
            patch.object(
                server,
                "run_server_async",
                new=fail_with_sensitive_detail,
            ),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            server.run_server()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("RuntimeError", stderr.getvalue())
        self.assertNotIn("sensitive", stderr.getvalue())
        self.assertNotIn("account-name", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
