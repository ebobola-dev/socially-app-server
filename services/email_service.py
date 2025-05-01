
from email.message import EmailMessage
from email.utils import make_msgid

from aiosmtplib import SMTP

from config.email_config import EmailConfig
from models.otp import OtpDestiny


class EmailService:
    @staticmethod
    async def send_otp(email, otp_value: str, destiny: OtpDestiny):
        message = EmailMessage()
        message["Subject"] = f"Your OTP code for {destiny.value} on Socially App"
        message["From"] = EmailConfig.ADDRESS
        message["To"] = email
        message["Message-ID"] = make_msgid()
        message.set_content(
            f"OTP code: {otp_value}\nThis code is valid for 15 minutes."
        )

        smtp = SMTP(
            hostname="smtp.yandex.ru",
            port=465,
            use_tls=True,
        )
        await smtp.connect()
        await smtp.login(EmailConfig.ADDRESS, EmailConfig.PASSWORD)
        await smtp.send_message(message)
        await smtp.quit()
