import asyncio
from io import BytesIO
from logging import Logger

from aiohttp.web import FileResponse, Request, json_response

from config.length_requirements import LengthRequirements
from config.server_config import ServerConfig
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
    ToManyImagesInPostError,
    ValidationError,
)
from models.pagination import Pagination
from models.post import Post
from repositories.post_repository import PostRepository
from services.file_service import FileService
from utils.image_utils import ImageUtils, PillowValidatationResult
from utils.my_validator.my_validator import ValidateField
from utils.my_validator.rules import CanCreateInstanceRule
from utils.sizes import SizeUtils


class PostsController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    @authenticate()
    async def get_all(self, request: Request):
        pagination = Pagination.from_request(request)
        user_id = request.query.get("user_id")
        posts = await PostRepository.get_all(
            session=request.db_session,
            user_id=user_id,
            pagination=pagination,
        )

        json_posts = tuple(
            map(
                lambda post: post.to_json(detect_is_liked_user_id=request.user_id),
                posts,
            )
        )
        json_result = {
            "count": len(posts),
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
            },
        }
        if user_id:
            json_result['user_id'] = user_id
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
        return json_response(data=post.to_json(detect_is_liked_user_id=request.user_id))

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
                        raise ToManyImagesInPostError()
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
                    pillow_validation_result = await asyncio.to_thread(
                        ImageUtils.is_valid_by_pillow, image_file_buffer
                    )
                    is_valid_by_filetype = await asyncio.to_thread(
                        ImageUtils.is_valid_by_filetype, image_file_buffer
                    )
                    if (
                        not is_valid_by_filetype
                        or pillow_validation_result == PillowValidatationResult.invalid
                    ):
                        raise InvalidImageError(field_name="image", filename=filename)
                    images.append(
                        {
                            "index": current_index,
                            "ext": file_ext,
                            "content": image_file_buffer,
                            "size": total_size,
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
            image_exts=list(map(lambda img_data: img_data["ext"], images)),
        )
        await PostRepository.add(session=request.db_session, new_post=new_post)
        self._logger.debug(f"New post: {new_post}")

        await FileService.save_post_images(
            post_id=new_post.id, images=images, logger=self._logger
        )

        return json_response(new_post.to_json())

    @authenticate()
    async def delete(self, request: Request):
        post_id = request.query.get("post_id")
        if not post_id:
            raise PostIdNotSpecifiedError()
        post = await PostRepository.get_by_id(
            session=request.db_session,
            post_id=post_id,
        )
        if not post:
            raise PostNotFoundError(post_id)
        if post.author_id != request.user_id:
            raise ForbiddenError(global_errors=["You can't delete someone else's post"])
        await FileService.delete_all_post_images(post_id=post_id)
        deleted_post = await PostRepository.soft_delete(
            session=request.db_session, target_post_id=post_id
        )
        return json_response(data=deleted_post.to_json())

    @authenticate()
    async def get_post_image(self, request: Request):
        post_id = request.match_info.get("post_id")
        image_index = request.query.get("index")
        ValidateField(field_name="index", rules=[CanCreateInstanceRule(int)])(
            image_index
        )
        image_index = int(image_index)
        post = await PostRepository.get_by_id(
            session=request.db_session, post_id=post_id
        )
        if not post:
            raise PostNotFoundError(post_id=post_id)
        max_image_index = len(post.image_exts) - 1
        if image_index < 0 or image_index > max_image_index:
            raise ValidationError(
                {
                    "index": f"must be between 0 and {max_image_index} (the post contain {max_image_index + 1} images)"
                }
            )
        image_ext = post.image_exts[image_index]
        image_path = await FileService.get_one_post_image_path(
            post_id=post_id,
            image_index=image_index,
            image_ext=image_ext,
        )
        return FileResponse(image_path)

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
        )
        return json_response(
            data=liked_post.to_json(detect_is_liked_user_id=request.user_id)
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
            data=updated_post.to_json(detect_is_liked_user_id=request.user_id)
        )
