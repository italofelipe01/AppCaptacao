import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app_captacao.core.config import environment


class WritableStateDirTests(unittest.TestCase):
    def test_writable_state_falls_back_when_appdata_is_denied(self):
        fallback_dir = Path(tempfile.gettempdir()) / f"appcaptacao_state_test_{uuid.uuid4().hex}"
        denied_dir = fallback_dir.parent / f"denied_{uuid.uuid4().hex}"

        def ensure_directory(path):
            if Path(path) == denied_dir:
                raise PermissionError(5, "Acesso negado", str(path))
            Path(path).mkdir(parents=True, exist_ok=True)
            return Path(path)

        try:
            with patch.object(environment, "get_state_dir", return_value=denied_dir), patch.object(
                environment, "get_temporary_state_dir", return_value=fallback_dir
            ), patch.object(environment, "_ensure_writable_directory", side_effect=ensure_directory):
                self.assertEqual(environment.get_writable_state_dir(), fallback_dir)
        finally:
            if fallback_dir.exists():
                fallback_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
