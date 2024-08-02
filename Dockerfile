FROM python:3.11-slim
# Define the application version as an argument
ARG APP_VERSION=0.7.3

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy the pyproject.toml and poetry.lock files into the container
COPY pyproject.toml poetry.lock /app/

# Install the dependencies
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Expose the port the application will run on
EXPOSE 8000

# Start the application
CMD ["uvicorn", "prodsys_api:app", "--host",  "0.0.0.0", "--port", "8000"]