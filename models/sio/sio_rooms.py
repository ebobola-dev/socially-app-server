class SioRooms:
    @staticmethod
    def get_authorized_room() -> str:
        return "authorized_room"

    @staticmethod
    def get_personal_room(user_id: str) -> str:
        return f"personal_room_{user_id}"

    @staticmethod
    def get_post_room(post_id: str) -> str:
        return f"post_room_{post_id}"
