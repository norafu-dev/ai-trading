import os


# Unit tests must remain runnable without PostgreSQL. Production configuration has
# no default and still requires DATABASE_URL from the environment.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
