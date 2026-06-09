import smtplib
import ssl

from email.mime.text import MIMEText
from config_loader import load_config

config = load_config()

smtp_cfg = config["smtp"]


def send_email(recipients, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["email"]
    msg["To"] = ",".join(recipients)

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        smtp_cfg["server"],
        smtp_cfg["port"],
        context=context
    ) as server:

        server.login(
            smtp_cfg["email"],
            smtp_cfg["password"]
        )

        server.sendmail(
            smtp_cfg["email"],
            recipients,
            msg.as_string()
        )