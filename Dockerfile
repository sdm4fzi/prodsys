ARG APP_VERSION=0.5.3
# TODO: update to gunicorn fastAPI -> https://github.com/tiangolo/full-stack-fastapi-template/blob/master/backend/Dockerfile

FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the poetry files into the container
COPY pyproject.toml poetry.lock /app/

# Install dependencies using Poetry
RUN pip install prodsys==0.5.3

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "prodsys_api:app", "--host",  "0.0.0.0", "--port", "8000"]