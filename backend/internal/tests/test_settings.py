import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase


class InternalSettingsTests(SimpleTestCase):
    def test_internal_settings_use_only_the_explicit_internal_database_path(self):
        with TemporaryDirectory() as temporary_directory:
            internal_path = Path(temporary_directory) / "internal.sqlite3"
            old_internal_path = os.environ.get("CIXIS_INTERNAL_DB_PATH")
            old_cixis_path = os.environ.get("CIXIS_DB_PATH")
            os.environ["CIXIS_INTERNAL_DB_PATH"] = str(internal_path)
            os.environ["CIXIS_DB_PATH"] = "/must-not-be-used/cixis.sqlite3"
            try:
                from internal_config import settings

                importlib.reload(settings)
                self.assertEqual(settings.DATABASES["default"]["NAME"], str(internal_path))
                self.assertNotIn("pos", settings.INSTALLED_APPS)
                self.assertFalse(settings.DEBUG)
                self.assertNotIn("corsheaders", settings.INSTALLED_APPS)
            finally:
                if old_internal_path is None:
                    os.environ.pop("CIXIS_INTERNAL_DB_PATH", None)
                else:
                    os.environ["CIXIS_INTERNAL_DB_PATH"] = old_internal_path
                if old_cixis_path is None:
                    os.environ.pop("CIXIS_DB_PATH", None)
                else:
                    os.environ["CIXIS_DB_PATH"] = old_cixis_path
