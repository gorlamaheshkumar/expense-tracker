"""Entry point. `python main.py` on desktop; Buildozer uses this on Android.

On Android we request the SMS permissions at runtime before the UI builds so
the AndroidSmsProvider can read the inbox. On desktop these imports are absent
and we silently fall back to the bundled sample SMS.
"""


def _request_android_permissions():
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_SMS,
            Permission.RECEIVE_SMS,
        ])
    except Exception:
        # Not on Android (or permissions module unavailable) - ignore.
        pass


if __name__ == "__main__":
    _request_android_permissions()
    from expense.app import main
    main()
