"""SMS source abstraction.

On a phone we read the real inbox via the Android content provider (pyjnius).
On Windows/Mac during development there is no inbox, so MockSmsProvider serves
realistic sample messages from data/sample_sms.json. The rest of the app only
ever sees `read_recent()` -> list[dict(id, sender, body, ts)], so screens never
know which backend they're talking to.
"""

import json
import os
import time


def _data_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "data", "sample_sms.json")


class SmsProvider:
    """Interface. Implementations return newest-first message dicts."""

    def is_available(self):
        return False

    def read_recent(self, limit=50):
        raise NotImplementedError


class MockSmsProvider(SmsProvider):
    """Reads canned messages so the full pipeline runs on desktop."""

    def __init__(self, path=None):
        self.path = path or _data_path()

    def is_available(self):
        return os.path.exists(self.path)

    def read_recent(self, limit=50):
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as fh:
            messages = json.load(fh)
        # Give relative timestamps anchored to "now" so the UI feels live,
        # while keeping the order defined in the file (newest first).
        now = int(time.time())
        out = []
        for i, msg in enumerate(messages[:limit]):
            out.append({
                "id": msg.get("id", "mock-%d" % i),
                "sender": msg.get("sender", ""),
                "body": msg.get("body", ""),
                "ts": now - msg.get("mins_ago", i * 30) * 60,
            })
        return out


class AndroidSmsProvider(SmsProvider):
    """Reads the device inbox via content://sms/inbox using pyjnius.

    Only instantiated on Android (see get_provider). Requires READ_SMS to have
    been granted at runtime; otherwise read_recent() returns [].
    """

    def is_available(self):
        try:
            import jnius  # noqa: F401
            return True
        except Exception:
            return False

    def read_recent(self, limit=50):
        try:
            from jnius import autoclass, cast
        except Exception:
            return []

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Uri = autoclass("android.net.Uri")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()

        uri = Uri.parse("content://sms/inbox")
        projection = ["_id", "address", "body", "date"]
        cursor = resolver.query(uri, projection, None, None, "date DESC")
        if cursor is None:
            return []

        out = []
        try:
            idx_id = cursor.getColumnIndex("_id")
            idx_addr = cursor.getColumnIndex("address")
            idx_body = cursor.getColumnIndex("body")
            idx_date = cursor.getColumnIndex("date")
            count = 0
            while cursor.moveToNext() and count < limit:
                out.append({
                    "id": "and-%s" % cursor.getString(idx_id),
                    "sender": cursor.getString(idx_addr) or "",
                    "body": cursor.getString(idx_body) or "",
                    # Android stores ms epoch; normalize to seconds
                    "ts": int(cursor.getLong(idx_date) / 1000),
                })
                count += 1
        finally:
            cursor.close()
        return out


def is_android():
    return "ANDROID_ARGUMENT" in os.environ or os.environ.get("KIVY_BUILD") == "android"


def get_provider():
    """Pick the real provider on a phone, the mock everywhere else."""
    if is_android():
        prov = AndroidSmsProvider()
        if prov.is_available():
            return prov
    return MockSmsProvider()
