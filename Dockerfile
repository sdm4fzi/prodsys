ARG APP_VERSION=0.8.3

FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy the pyproject.toml and poetry.lock files into the container
COPY pyproject.toml poetry.lock /app/

# TODO: Install dependencies using Poetry instead of pypi
RUN pip install prodsys==0.8.3

# Copy the rest of the application code
COPY . /app

# Expose the port the application will run on
EXPOSE 8000

# Start the application
CMD ["uvicorn", "prodsys_api:app", "--host",  "0.0.0.0", "--port", "8000"]