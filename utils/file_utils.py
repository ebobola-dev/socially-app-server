import hashlib
from io import BytesIO

class FileUtils:
	def calculate_sha256_from_bytesio(data: BytesIO) -> str:
		sha256_hash = hashlib.sha256()
		data.seek(0)
		for chunk in iter(lambda: data.read(4096), b""):
			sha256_hash.update(chunk)
		return sha256_hash.hexdigest()