: "${DB_USER:?}" "${DB_PASSWORD:?}" "${DB_NAME:?}" "${DB_INSTANCE:?}"
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_INSTANCE}"
