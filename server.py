import asyncio
import sys

import socketio
from aiohttp import web

from config.database_config import DatabaseConfig
from config.email_config import EmailConfig
from config.jwt_config import JwtConfig
from config.logger_config import MyLoggerConfig
from config.minio_config import MinioConfig
from config.paths import Paths
from config.server_config import ServerConfig
from controllers.apk_update_controller import ApkUpdatesController
from controllers.auth_conrtoller import AuthConrtoller
from controllers.comments_controller import CommentsController
from controllers.media_controller import MediaController
from controllers.middlewares import Middlewares
from controllers.posts_controller import PostsController
from controllers.registration_controller import RegistrationController
from controllers.sio_controller import SioController
from controllers.test_users_controller import TestUsersController
from controllers.users_controller import UsersController
from database.database import Database
from models.comment import Comment  # noqa: F401
from models.post import Post  # noqa: F401
from models.post_likes import post_likes  # noqa: F401
from models.user import User  # noqa: F401
from services.minio_service import MinioService
from services.session_store import SessionStore
from services.test_users import TestUsers


async def initialize():
    ServerConfig.initialize()  #! Must be called first (loaging env variables)
    DatabaseConfig.initialize()
    JwtConfig.initialize()
    EmailConfig.initialize()
    MyLoggerConfig.initialize()
    MinioConfig.initialize()
    await SessionStore.initialize()
    await MinioService.initialize()
    await Database.initialize()


async def main():
    await initialize()

    from services.my_logger import MyLogger

    server_logger = MyLogger.get_logger("Server")
    server_logger.info(
        f"Initialized with logging level: {MyLoggerConfig.LEVEL}, run in docker: {ServerConfig.RUN_IN_DOCKER}\n"
    )

    try:
        test_users_service = TestUsers(logger=MyLogger.get_logger("Test Users Service"))
        await test_users_service.create_test_users()
    except Exception as test_users_error:
        server_logger.warning(f"Error on creating test users: {test_users_error}\n")

    try:
        await Database.after_initialize()
        server_logger.debug("User sids has been reset\n")
    except Exception as reset_sids_error:
        server_logger.warning(f"Error on reset sids: {reset_sids_error}")

    middlewares = Middlewares(MyLogger.get_logger("Middlewares"))

    sio = socketio.AsyncServer(
        async_mode="aiohttp", async_handlers=True, cors_allowed_origins="*"
    )
    app = web.Application(
        middlewares=(
            middlewares.error_middleware,
            middlewares.database_session,
        ),
    )
    sio.attach(app)
    main_sio_namespace = SioController(
        logger=MyLogger.get_logger("Socket IO"),
        namespace="/",
    )
    sio.register_namespace(main_sio_namespace)

    registration_controller = RegistrationController(
        logger=MyLogger.get_logger("Registration")
    )
    auth_controller = AuthConrtoller(
        logger=MyLogger.get_logger("Auth"),
        main_sio_namespace=main_sio_namespace,
    )
    users_controller = UsersController(
        logger=MyLogger.get_logger("Users"),
        main_sio_namespace=main_sio_namespace,
    )
    test_users_controller = TestUsersController(
        logger=MyLogger.get_logger("Test Users"),
        main_sio_namespace=main_sio_namespace,
    )
    apk_updates_controller = ApkUpdatesController(
        logger=MyLogger.get_logger("Apk Updates"),
        main_sio_namespace=main_sio_namespace,
    )
    posts_controller = PostsController(
        logger=MyLogger.get_logger("Posts"),
        main_sio_namespace=main_sio_namespace,
    )
    comments_controller = CommentsController(
        logger=MyLogger.get_logger("Commetns"),
        main_sio_namespace=main_sio_namespace,
    )
    media_controller = MediaController(logger=MyLogger.get_logger("Media"))

    app.add_routes(
        [
            web.post(
                Paths.Registration.CHECK_EMAIL, registration_controller.check_email
            ),
            web.post(Paths.Registration.VERIFY_OTP, registration_controller.check_otp),
            web.put(
                Paths.Registration.COMPLETE_REGISTRATION,
                registration_controller.complete_registration,
            ),
            #
            web.post(Paths.Auth.LOGIN, auth_controller.login),
            web.post(
                Paths.Auth.ResetPassword.SEND_OTP,
                auth_controller.send_otp_to_reset_password,
            ),
            web.post(
                Paths.Auth.ResetPassword.VERIFY_OTP,
                auth_controller.verify_otp_for_reset_password,
            ),
            web.post(Paths.Auth.REFRESH, auth_controller.refresh),
            web.put(Paths.Auth.LOGOUT, auth_controller.logout),
            #
            web.get(Paths.Users.CHECK_USERNAME, users_controller.check_username),
            web.get(Paths.Users.GET_BY_ID, users_controller.get_by_id),
            web.get(Paths.Users.SEARCH, users_controller.search),
            web.put(Paths.Users.UPDATE_PROFILE, users_controller.update_profile),
            web.put(Paths.Users.UPDATE_PASSWORD, users_controller.update_password),
            web.put(Paths.Users.UPDATE_AVATAR, users_controller.update_avatar),
            web.delete(Paths.Users.DELETE_AVATAR, users_controller.delete_avatar),
            web.put(Paths.Users.FOLLOW, users_controller.follow),
            web.delete(Paths.Users.UNFOLLOW, users_controller.unfollow),
            web.get(Paths.Users.GET_FOLLOWINGS, users_controller.get_followings),
            web.get(Paths.Users.GET_FOLLOWERS, users_controller.get_followers),
            web.put(Paths.Users.UPDATE_ROLE, users_controller.update_role),
            web.delete(Paths.Users.DELETE, users_controller.soft_delete),
            #
            web.get(
                Paths.TestUsers.ADMIN_ROLE_TEST, test_users_controller.test_admin_role
            ),
            web.get(
                Paths.TestUsers.OWNER_ROLE_TEST, test_users_controller.test_owner_role
            ),
            #
            web.post(Paths.ApkUpdates.ADD, apk_updates_controller.add),
            web.get(Paths.ApkUpdates.GET_ONE, apk_updates_controller.get_one),
            web.get(Paths.ApkUpdates.GET_MANY, apk_updates_controller.get_many),
            web.delete(Paths.ApkUpdates.DELETE, apk_updates_controller.delete),
            #
            web.get(Paths.Posts.GET_ALL, posts_controller.get_all),
            web.get(Paths.Posts.GET_ONE, posts_controller.get_one),
            web.delete(Paths.Posts.DELETE, posts_controller.delete),
            web.post(Paths.Posts.CREATE, posts_controller.create),
            web.post(Paths.Posts.LIKE, posts_controller.like),
            web.delete(Paths.Posts.UNLIKE, posts_controller.unlike),
            web.get(Paths.Posts.Comments.GET_ALL, comments_controller.get_all),
            web.post(Paths.Posts.Comments.CREATE, comments_controller.add),
            web.delete(Paths.Posts.Comments.DELETE, comments_controller.delete),
            #
            # web.get(Paths.Media.AVATARS, media_controller.get_avatar_image),
            # web.get(Paths.Media.POSTS, media_controller.get_post_image),
            # web.get(Paths.Media.MESSAGES, media_controller.get_message_image),
            web.get(Paths.Media.UNIVERSAL, media_controller.get),
            web.get(Paths.Media.WITH_FOLDER, media_controller.get_with_folder),
        ]
    )

    from services.background_services import BackgroundServices

    app.on_startup.append(BackgroundServices.start_background_tasks)
    app.on_cleanup.append(BackgroundServices.cleanup_background_tasks)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
    )

    await site.start()
    server_logger.info(
        f"Server started on {ServerConfig.HOST}:{ServerConfig.PORT}...\n"
    )

    while True:
        await asyncio.sleep(3600)


def run_server():
    if sys.platform != "win32":
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())


if __name__ == "__main__":
    run_server()
