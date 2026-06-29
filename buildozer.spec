[app]

# (str) Title of your application
title = Expense Tracker

# (str) Package name
package.name = expensetracker

# (str) Package domain (needed for android/ios packaging)
package.domain = in.mahesh.expense

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (list) Application requirements
# pyjnius -> SMS content provider; android -> runtime permissions
requirements = python3,kivy==2.3.1,pyjnius,android

# (str) Application versioning
version = 0.1.0

# (str) Supported orientation (portrait for a phone budget app)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
# READ_SMS + RECEIVE_SMS are the core of the auto-tracking feature.
android.permissions = READ_SMS, RECEIVE_SMS

# (int) Target Android API, should be as high as possible.
android.api = 34

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
# android.ndk = 25b

# (list) The Android archs to build for
# arm64-v8a only: covers essentially every phone from the last ~8 years and
# halves build time vs. also building armeabi-v7a.
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = 1

# (str) Presplash / icon (add your own assets later)
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
