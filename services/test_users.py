import json
from logging import Logger
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from database.database import Database
from models.avatar_type import AvatarType
from models.gender import Gender
from models.role import Role
from repositories.user_repository import UserRepository
from utils.date_generator import generate_date
from utils.password_generator import generate_password


class TestUsers:
    def __init__(self, logger: Logger, test_users_file="test_users.json"):
        self._logger = logger
        self._test_users_file = test_users_file

    def _get_test_users_data(self):
        with open(self._test_users_file, encoding="utf-8") as file:
            return json.load(file)

    async def _check_user_exist(self, session: AsyncSession, email):
        user = await UserRepository.get_by_email(session, email)
        return email, bool(user)

    async def _get_non_existent_users(
        self, session: AsyncSession, emails: Iterable[str]
    ) -> tuple[str]:
        result = []
        for email in emails:
            check_res = await self._check_user_exist(session, email)
            result.append(check_res)
        non_existent_emails = tuple(email for email, is_exist in result if not is_exist)
        return non_existent_emails

    async def _create_test_user(self, user_data):
        async with Database.session_maker() as session:
            try:
                email = user_data.get("email_address")
                # ? Registration
                new_user = await UserRepository.create_new(
                    session=session,
                    email=email,
                    role=Role(user_data.get("role")),
                )
                # ? Complete registration
                await UserRepository.complete_registration(
                    session=session,
                    user_id=new_user.id,
                    date_of_birth=generate_date(),
                    username=user_data.get("username"),
                    password=generate_password(),
                    fullname=user_data.get("fullname"),
                    gender=Gender(user_data.get("gender")),
                    about_me=user_data.get("about_me"),
                )
                # ? Update avatar type
                if user_data.get("avatar_type"):
                    await UserRepository.update_avatar(
                        session=session,
                        user_id=new_user.id,
                        new_avatar_type=AvatarType(user_data.get("avatar_type")),
                    )
                await session.commit()
                return True
            except Exception as error:
                await session.rollback()
                self._logger.debug(
                    f"Error on creating {user_data.get('email_address')}: {error}"
                )
                return False

    async def create_test_users(self) -> None:
        try:
            self._logger.debug(
                f"Creating test users, reading ({self._test_users_file})..."
            )
            test_users_data = self._get_test_users_data()
            count = len(test_users_data)
            self._logger.debug(f"Got ({count}) users from json file, checking exists")
            async with Database.session_maker() as session:
                non_existent_emails = await self._get_non_existent_users(
                    session,
                    (json_user.get("email_address") for json_user in test_users_data),
                )
            if not non_existent_emails:
                self._logger.info(
                    f"No non-existing test users were found (by {count} emails)\n"
                )
                return
            self._logger.debug(
                f"({len(non_existent_emails)}) emails that don't exist, creating..."
            )
            non_existent_users_data = tuple(
                test_user_data
                for test_user_data in test_users_data
                if test_user_data.get("email_address") in non_existent_emails
            )
            creation_result = []
            for user_data in non_existent_users_data:
                one_creation_result = await self._create_test_user(user_data)
                creation_result.append(one_creation_result)
            self._logger.info(f"Created ({creation_result.count(True)}) test users\n")
        except Exception as error:
            self._logger.warning(f"Error on creating test users: {error}\n")
