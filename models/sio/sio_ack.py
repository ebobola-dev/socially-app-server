class SioAck:
	def __init__(
		self,
		success: bool = True,
		data: dict | None = None,
		error_text: str = '?',
	):
		self._success = success
		self._data = data
		self._error_text = error_text

	@staticmethod
	def success(data: dict | None = None):
		return SioAck(
			success = True,
			data = data,
		)

	@staticmethod
	def failed(error_text: str = '?'):
		return SioAck(
			success = False,
			error_text = error_text,
		)

	def to_json(self):
		json_view = {
			'success': self._success,
		}
		if self._success:
			json_view['data'] = self._data
		else:
			json_view['error_text'] = self._error_text
		return json_view