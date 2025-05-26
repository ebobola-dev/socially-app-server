from enum import Enum


class ApiConflictType(Enum):
    ALREADY_FOLLOWING = 1
    NOT_FOLLOWING = 2
    ALREADY_LIKED = 3
    NOT_LIKED = 4