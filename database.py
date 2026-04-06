import os
import psycopg2

def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url, sslmode="require")

    return psycopg2.connect(
        host="localhost",
        database="clothing_db",
        user="postgres",
        password=os.getenv("DB_PASSWORD", "")
    )