import asyncio
from io import BytesIO
from logging import Logger

from aiohttp.web import Request, json_response

from config.length_requirements import LengthRequirements
from config.server_config import ServerConfig
from controllers.helpers import parse_short_flag
from controllers.middlewares import authenticate, content_type_is_multipart
from controllers.sio_controller import SioController
from models.exceptions.api_exceptions import (
    BadImageFileExtError,
    ForbiddenError,
    ImageIsTooLargeError,
    InvalidImageError,
    PostIdNotSpecifiedError,
    PostNoImagesError,
    PostNotFoundError,
    TooManyImagesInPostError,
    ValidationError,
)
from models.pagination import Pagination
from models.post import Post
from repositories.post_repository import PostRepository
from services.minio_service import Buckets, MinioService
from utils.image_utils import ImageUtils, VerifyImageError
from utils.sizes import SizeUtils


class PostsController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    @authenticate()
    async def get_all(self, request: Request):
        pagination = Pagination.from_request(request)
        user_id = request.query.get("user_id")
        short = parse_short_flag(request.query)
        posts = await PostRepository.get_all(
            session=request.db_session,
            user_id=user_id,
            pagination=pagination,
        )

        json_posts = tuple(
            map(
                lambda post: post.to_json(
                    detect_rels_for_user_id=request.user_id, short=short
                ),
                posts,
            )
        )
        json_result = {
            "count": len(posts),
            "pagination": {
                "offset": pagination.offset,
                "limit": pagination.limit,
            },
        }
        if user_id:
            json_result["user_id"] = user_id
        json_result["posts"] = json_posts
        return json_response(data=json_result)

    @authenticate()
    async def get_one(self, request: Request):
        post_id = request.match_info["post_id"]
        post = await PostRepository.get_by_id_with_relations(
            session=request.db_session,
            post_id=post_id,
            include_deleted=True,
        )
        if not post:
            raise PostNotFoundError(post_id)
        return json_response(data=post.to_json(detect_rels_for_user_id=request.user_id))

    @authenticate()
    @content_type_is_multipart()
    async def create(self, request: Request):
        reader = await request.multipart()
        text_content: str = ""
        images = []

        async for part in reader:
            match part.name:
                case "text":
                    if part.filename:
                        raise ValidationError({"text": "must be a string field"})
                    try:
                        text_content = (await part.text()).strip()
                    except Exception:
                        raise ValidationError({"text": "must be a string field"})
                case "images":
                    current_index = len(images)
                    if current_index == ServerConfig.MAX_IMAGES_IN_POST:
                        raise TooManyImagesInPostError()
                    filename = part.filename
                    if not filename:
                        raise ValidationError(
                            {"images": "must be an array of files(images)"}
                        )
                    file_ext = filename[filename.rfind(".") :]
                    if (
                        not file_ext
                        or file_ext == "."
                        or file_ext[1:] not in ServerConfig.ALLOWED_IMAGE_EXTENSIONS
                    ):
                        raise BadImageFileExtError(file_ext)
                    image_file_buffer = BytesIO()
                    total_size = 0
                    while chunk := await part.read_chunk(4096):
                        total_size += len(chunk)
                        if total_size > ServerConfig.MAX_IMAGE_SIZE * 1024 * 1024:
                            raise ImageIsTooLargeError()
                        image_file_buffer.write(chunk)
                    image_file_buffer.seek(0)
                    try:
                        image_file_buffer = await ImageUtils.verify_image(
                            source_buffer=image_file_buffer,
                            source_extension=file_ext,
                        )
                    except VerifyImageError as img_verify_error:
                        if img_verify_error.message == 'Unable to convert by magick':
                            self._logger.exception(img_verify_error)
                        raise InvalidImageError(
                            field_name="images",
                            filename=filename,
                            server_message=img_verify_error.message,
                        )
                    images.append(
                        {
                            "index": current_index,
                            "ext": file_ext,
                            "content": image_file_buffer,
                            "size": total_size,
                            "file_key": f"{current_index}{file_ext}",
                        }
                    )

        self._logger.debug(f"[CREATE] text_content: {text_content}, images:")
        for image_data in images:
            self._logger.debug(
                f"[CREATE]    index: {image_data['index']}, ext: {image_data['ext']}, size: {SizeUtils.bytes_to_human_readable(image_data['size'])}"
            )

        if len(text_content) > LengthRequirements.MessageTextContent.MAX:
            raise ValidationError(
                {"text": f"max len: {LengthRequirements.MessageTextContent.MAX}"}
            )
        if not images:
            raise PostNoImagesError()

        new_post = Post.new(
            author_id=request.user_id,
            text_content=text_content,
            images_count=len(images),
        )
        await PostRepository.add(session=request.db_session, new_post=new_post)
        self._logger.debug(f"New post: {new_post}")

        for image in images:
            splitted_images = await asyncio.to_thread(
                ImageUtils.split_image_sync,
                image_buffer=image["content"],
            )
            for size, buffer in splitted_images.items():
                await MinioService.save(
                    bucket=Buckets.posts,
                    key=f"{new_post.id}/{image['index']}/{size.str_view}{image['ext']}",
                    bytes=buffer,
                )

        return json_response(new_post.to_json(detect_rels_for_user_id=request.user_id))

    @authenticate()
    async def delete(self, request: Request):
        post_id = request.query.get("post_id")
        if not post_id:
            raise PostIdNotSpecifiedError()
        post = await PostRepository.get_by_id_with_relations(
            session=request.db_session,
            post_id=post_id,
        )
        if not post:
            raise PostNotFoundError(post_id)
        if post.author_id != request.user_id and not request.user_role.is_owner:
            raise ForbiddenError(global_errors=["You can't delete someone else's post"])
        deleted_post = await PostRepository.soft_delete(
            session=request.db_session, target_post_id=post_id
        )
        await MinioService.delete_all_by_prefix(
            bucket=Buckets.posts,
            prefix=post.id,
        )
        await self._sio.emit_post_deleted(post_id=post_id)
        return json_response(
            data=deleted_post.to_json(detect_rels_for_user_id=request.user_id)
        )

    @authenticate()
    async def like(self, request: Request):
        post_id = request.query.get("post_id")
        self._logger.debug(f"[LIKES] post_id: {post_id}\n")
        if not post_id:
            raise PostIdNotSpecifiedError()
        liked_post = await PostRepository.like(
            session=request.db_session,
            target_post_id=post_id,
            user_id=request.user_id,
            logger=self._logger,
        )
        return json_response(
            data=liked_post.to_json(detect_rels_for_user_id=request.user_id)
        )

    @authenticate()
    async def unlike(self, request: Request):
        post_id = request.query.get("post_id")
        self._logger.debug(f"[LIKES] post_id: {post_id}\n")
        if not post_id:
            raise PostIdNotSpecifiedError()
        updated_post = await PostRepository.unlike(
            session=request.db_session,
            target_post_id=post_id,
            user_id=request.user_id,
        )
        return json_response(
            data=updated_post.to_json(detect_rels_for_user_id=request.user_id)
        )
