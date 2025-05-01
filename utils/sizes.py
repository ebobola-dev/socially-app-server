class SizeUtils:
    @staticmethod
    def bytes_to_human_readable(size_in_bytes: int):
        units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

        unit_index = 0
        while size_in_bytes >= 1024 and unit_index < len(units) - 1:
            size_in_bytes /= 1024
            unit_index += 1

        return f"{size_in_bytes:.2f} {units[unit_index]}"
