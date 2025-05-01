class LengthRequirements:
    class Fullname:
        MAX = 32

    class AboutMe:
        MAX = 256

    class Username:
        MIN = 4
        MAX = 16
        TEXT = f"lowercase latin, number, underscore and dots only, between {MIN} and {MAX} chracters, cannot start with a dot or a number, cannot consist of only numbers"

    class Password:
        MIN = 8
        MAX = 16
        TEXT = f"at least one letter, at least one digit, between {MIN} and {MAX} characters"
