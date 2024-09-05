ARG APP_VERSION=0.8.0

FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the poetry files into the container
COPY pyproject.toml poetry.lock /app/

# TODO: Install dependencies using Poetry instead of pypi
RUN pip install prodsys==0.8.0



COPY . /app

EXPOSE 8000

CMD ["uvicorn", "prodsys_api:app", "--host",  "0.0.0.0", "--port", "8000"]