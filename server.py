import sys
import asyncio
import socketio
from aiohttp import web

from config.server_config import SERVER_CONFIG
from config.database_config import DATABASE_CONFIG
from config.jwt_config import JWT_CONFIG
from config.email_config import EMAIL_CONFIG
from config.paths import PATHS
from config.logger_config import MY_LOGGER_CONFIG

from database.database import Database
from controllers.middlewares import Middlewares
from controllers.registration_controller import RegistrationController
from controllers.auth_conrtoller import AuthConrtoller
from controllers.users_controller import UsersController
from controllers.sio_controller import SioController
from controllers.test_users_controller import TestUsersController
from controllers.apk_update_controller import ApkUpdatesController

from services.test_users import TestUsers

async def initialize():
	SERVER_CONFIG.initialize() #! Must be called first (loaging env variables)
	DATABASE_CONFIG.initialize()
	JWT_CONFIG.initialize()
	EMAIL_CONFIG.initialize()
	MY_LOGGER_CONFIG.initialize()
	await Database.initialize()

async def main():
	await initialize()

	from services.my_logger import MyLogger
	server_logger = MyLogger.get_logger('Server')
	server_logger.info(f'Initialized with logging level: {MY_LOGGER_CONFIG.LEVEL}, run in docker: {SERVER_CONFIG.RUN_IN_DOCKER}\n')

	try:
		test_users_service = TestUsers(
			logger = MyLogger.get_logger('Test Users Service')
		)
		await test_users_service.create_test_users()
	except Exception as test_users_error:
		server_logger.warning(f'Error on creating test users: {test_users_error}\n')

	try:
		await Database.after_initialize()
		server_logger.debug(f'User sids has been reset\n')
	except Exception as reset_sids_error:
		server_logger.warning(f'Error on reset sids: {reset_sids_error}')

	middlewares = Middlewares(MyLogger.get_logger('Middlewares'))

	sio = socketio.AsyncServer(async_mode='aiohttp', async_handlers=True, cors_allowed_origins='*')
	app = web.Application(
		middlewares = (
			middlewares.error_middleware,
			middlewares.content_type_is_json,
			middlewares.content_type_is_multipart_formdata,
			middlewares.check_device_id,
			middlewares.database_session,
			middlewares.check_authorized,
			middlewares.registration_completed,
			middlewares.admin_role,
			middlewares.owner_role,
		),
	)
	sio.attach(app)
	main_sio_namespace = SioController(
		logger = MyLogger.get_logger('Socket IO'),
		namespace = '/',
	)
	sio.register_namespace(main_sio_namespace)

	registration_controller = RegistrationController(
		logger = MyLogger.get_logger('Registration')
	)
	auth_controller = AuthConrtoller(
		logger = MyLogger.get_logger('Auth'),
		main_sio_namespace = main_sio_namespace,
	)
	users_controller = UsersController(
		logger = MyLogger.get_logger('Users'),
		main_sio_namespace = main_sio_namespace,
	)
	test_users_controller = TestUsersController(
		logger = MyLogger.get_logger('Test Users'),
		main_sio_namespace = main_sio_namespace,
	)
	apk_updates_controller = ApkUpdatesController(
		logger = MyLogger.get_logger('Apk Updates'),
		main_sio_namespace = main_sio_namespace,
	)

	app.add_routes([
		web.post(PATHS.REGISTRATION.CHECK_EMAIL, registration_controller.check_email),
		web.post(PATHS.REGISTRATION.VERIFY_OTP, registration_controller.check_otp),
		web.put(PATHS.REGISTRATION.COMPLETE_REGISTRATION, registration_controller.complete_registration),

		web.post(PATHS.AUTH.LOGIN, auth_controller.login),
		web.post(PATHS.AUTH.RESET_PASSWORD.SEND_OTP, auth_controller.send_otp_to_reset_password),
		web.post(PATHS.AUTH.RESET_PASSWORD.VERIFY_OTP, auth_controller.verify_otp_for_reset_password),
		web.post(PATHS.AUTH.REFRESH, auth_controller.refresh),
		web.put(PATHS.AUTH.LOGOUT, auth_controller.logout),

		web.get(PATHS.USERS.CHECK_USERNAME, users_controller.check_username),
		web.get(PATHS.USERS.GET_BY_ID, users_controller.get_by_id),
		web.get(PATHS.USERS.SEARCH, users_controller.search),
		web.put(PATHS.USERS.UPDATE_PROFILE, users_controller.update_profile),
		web.put(PATHS.USERS.UPDATE_PASSWORD, users_controller.update_password),
		web.put(PATHS.USERS.UPDATE_AVATAR, users_controller.update_avatar),
		web.delete(PATHS.USERS.DELETE_AVATAR, users_controller.delete_avatar),
		web.get(PATHS.USERS.GET_AVATAR_IMAGE, users_controller.get_avatar_image),
		web.put(PATHS.USERS.FOLLOW, users_controller.follow),
		web.delete(PATHS.USERS.UNFOLLOW, users_controller.unfollow),
		web.get(PATHS.USERS.GET_FOLLOWINGS, users_controller.get_followings),
		web.get(PATHS.USERS.GET_FOLLOWERS, users_controller.get_followers),
		web.put(PATHS.USERS.UPDATE_ROLE, users_controller.update_role),

		#web.get(PATHS.TEST_USERS.ADMIN_ROLE_TEST, test_users_controller.test_admin_role),
		#web.get(PATHS.TEST_USERS.OWNER_ROLE_TEST, test_users_controller.test_owner_role),

		web.post(PATHS.APK_UPDATES.ADD, apk_updates_controller.add),
		web.get(PATHS.APK_UPDATES.GET_ONE, apk_updates_controller.get_one),
		web.get(PATHS.APK_UPDATES.GET_MANY, apk_updates_controller.get_many),
		web.get(PATHS.APK_UPDATES.DOWNLOAD, apk_updates_controller.download),
		web.delete(PATHS.APK_UPDATES.DELETE, apk_updates_controller.delete),
	])

	from services.background_services import BackgroundServices
	app.on_startup.append(BackgroundServices.start_background_tasks)
	app.on_cleanup.append(BackgroundServices.cleanup_background_tasks)

	runner = web.AppRunner(app)
	await runner.setup()

	site = web.TCPSite(
		runner,
		host=SERVER_CONFIG.HOST,
		port=SERVER_CONFIG.PORT,
	)

	await site.start()
	server_logger.info(f'Server started on {SERVER_CONFIG.HOST}:{SERVER_CONFIG.PORT}...\n')

	while True: await asyncio.sleep(3600)

def run_server():
	if sys.platform != "win32":
		import uvloop
		asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
	asyncio.run(main())

if __name__ == '__main__':
	run_server()