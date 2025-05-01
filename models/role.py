from enum import Enum


class Role(Enum):
	user = 1
	admin = 2
	owner = 3

	@property
	def is_admin(self): return self.value >= Role.admin.value

	@property
	def is_owner(self): return self == Role.owner