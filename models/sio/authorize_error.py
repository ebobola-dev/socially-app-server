class AuthorizeError(Exception):
	def __init__(
		self,
		internal_message: str = 'Error on authorize',
		ack_message: str = 'Something went wrong',
	):
		self.internal_message = internal_message
		self.ack_message = ack_message