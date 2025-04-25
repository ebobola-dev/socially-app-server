class LENGTH_REQIREMENTS:
	class FULLNAME:
		MAX = 32
	class ABOUT_ME:
		MAX = 256

	class USERNAME:
		MIN = 4
		MAX = 16
		TEXT = f'lowercase latin, number, underscore and dots only, between {MIN} and {MAX} chracters, cannot start with a dot or a number, cannot consist of only numbers'

	class PASSWORD:
		MIN = 8
		MAX = 16
		TEXT = f'at least one letter, at least one digit, between {MIN} and {MAX} characters'