from logging import Logger

from aiohttp.web import Request, json_response

from config.length_requirements import LengthRequirements
from controllers.middlewares import authenticate, content_type_is_json
from controllers.sio_controller import SioController
from models.comment import Comment
from models.exceptions.api_exceptions import (
    CommentIdNotSpecifiedError,
    CommentNotFoundError,
    ForbiddenToDeleteCommentError,
    PostNotFoundError,
    ValidationError,
)
from models.pagination import Pagination
from repositories.comments_repository import CommentsRepository
from repositories.post_repository import PostRepository
from repositories.user_repository import UserRepository
from utils.my_validator.my_validator import ValidateField, validate_request_body
from utils.my_validator.rules import IsInstanceRule, LengthRule


class CommentsController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    @authenticate()
    async def get_all(self, request: Request):
        pagination = Pagination.from_request(request)
        post_id = request.match_info.get("post_id")
        target_post = await PostRepository.get_by_id(
            session=request.db_session,
            post_id=post_id,
        )
        if not target_post:
            raise PostNotFoundError(post_id)
        comments = await CommentsRepository.get_all_by_post_id(
            session=request.db_session,
            post_id=post_id,
            pagination=pagination,
        )

        json_comments = tuple(
            map(
                lambda comment: comment.to_json(
                    include_reply=True, detect_rels_for_user_id=request.user_id
                ),
                comments,
            )
        )

        return json_response(
            data={
                "count": len(json_comments),
                "pagination": {
                    "offset": pagination.offset,
                    "limit": pagination.limit,
                },
                "post_id": post_id,
                "comments": json_comments,
            }
        )

    @authenticate()
    async def delete(self, request: Request):
        comment_id = request.query.get("comment_id")
        if not comment_id:
            raise CommentIdNotSpecifiedError()
        comment = await CommentsRepository.get_by_id(
            session=request.db_session,
            comment_id=comment_id,
        )
        self._logger.debug(f"comment: {comment}, bool: {bool(comment)}")
        if not comment:
            raise CommentNotFoundError(comment_id)
        post = await PostRepository.get_by_id_with_relations(
            session=request.db_session, post_id=comment.post_id
        )
        if not post:
            raise PostNotFoundError(comment.post_id)

        is_our_post = post.author_id == request.user_id
        is_our_comment = comment.author_id == request.user_id

        if not is_our_post and not is_our_comment and not request.user_role.is_owner:
            raise ForbiddenToDeleteCommentError()

        await CommentsRepository.hard_delete(
            session=request.db_session,
            target_comment_id=comment_id,
        )
        await self._sio.emit_comment_deleted(post_id=post.id, comment_id=comment_id)
        await self._sio.emit_post_comments_count_changed(
            post_id=post.id, new_comments_count=len(post.comments)
        )
        return json_response()

    @authenticate()
    @content_type_is_json()
    @validate_request_body(
        ValidateField(
            field_name="text_content",
            rules=[
                IsInstanceRule(str),
                LengthRule(min_length=1, max_length=LengthRequirements.Comment.MAX),
            ],
        ),
        ValidateField(
            field_name="reply_to_comment_id",
            nullable=False,
            required=False,
            rules=[
                IsInstanceRule(str),
            ],
        ),
    )
    async def add(self, request: Request):
        post_id = request.match_info.get("post_id")
        target_post = await PostRepository.get_by_id_with_relations(
            session=request.db_session,
            post_id=post_id,
        )
        if not target_post:
            raise PostNotFoundError(post_id)
        body: dict = request["validated_body"]
        text_content = body.get("text_content")
        reply_to_comment_id = body.get("reply_to_comment_id")
        if reply_to_comment_id:
            reply_to_comment = await CommentsRepository.get_by_id_with_relations(
                session=request.db_session, comment_id=reply_to_comment_id
            )
            if not reply_to_comment:
                raise CommentNotFoundError(reply_to_comment_id)
            if reply_to_comment.post_id != post_id:
                raise ValidationError(
                    {
                        "reply_to_comment_id": "the target comment belongs to another post"
                    }
                )

        new_comment = Comment.new(
            author_id=request.user_id,
            post_id=post_id,
            text_content=text_content,
            reply_to_comment_id=reply_to_comment_id,
        )
        await CommentsRepository.add(
            session=request.db_session,
            new_comment=new_comment,
        )
        post_author = await UserRepository.get_by_id(
            session=request.db_session,
            user_id=target_post.author_id,
        )
        await self._sio.emit_new_comment(
            new_comment=new_comment,
            post_author_sid=post_author.current_sid,
        )
        await self._sio.emit_post_comments_count_changed(
            post_id=post_id, new_comments_count=len(target_post.comments)
        )
        return json_response(
            data=new_comment.to_json(
                include_reply=reply_to_comment_id is not None,
                detect_rels_for_user_id=request.user_id,
            )
        )
