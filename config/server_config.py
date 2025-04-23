from os import getenv

from models.exceptions.initalize_exceptions import UnableToInitializeService

class SERVER_CONFIG:
	INITIALIZED: bool = False
	HOST: str
	PORT: int
	OWNER_KEY: str
	BCRYPT_SALT_ROUNDS = 4
	ALLOWED_IMAGE_EXTENSIONS = ('jpg', 'jpeg',  'png', 'webp',)
	MAX_IMAGE_SIZE = 7 #? in MB
	OTP_CODE_DURABILITY_MIN = 15
	RUN_IN_DOCKER = False

	@staticmethod
	def initialize():
		try:
			SERVER_CONFIG.RUN_IN_DOCKER = bool(getenv('RUN_IN_DOCKER'))
			if not SERVER_CONFIG.RUN_IN_DOCKER:
				from dotenv import load_dotenv
				load_dotenv(override=True)
			SERVER_CONFIG.HOST = getenv('SERVER_HOST')
			SERVER_CONFIG.PORT = int(getenv('SERVER_PORT'))
			SERVER_CONFIG.OWNER_KEY = getenv('OWNER_KEY')
			SERVER_CONFIG.INITIALIZED = True
		except Exception as error:
			raise UnableToInitializeService('SERVER_CONFIG') from error
