import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "afsalhameeth271103@gmail.com"
    MAIL_PASSWORD = "upbrpmkixwzsvfwu"
    MAIL_DEFAULT_SENDER = "afsalhameeth271103@gmail.com"
    WTF_CSRF_ENABLED = False
