class RE_PATTERNS:
	EMAIL = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
	USERNAME = r'^(?![0-9])(?!\d+$)(?!\.)[a-z0-9_.]{4,16}$'
	PASSWORD = r'^(?=.*[a-zA-Z])(?=.*\d).{8,16}$'
	APK_UPDATE_FILE = r'^socially_app-v(?P<version>\d+\.\d+\.\d+)\.apk$'