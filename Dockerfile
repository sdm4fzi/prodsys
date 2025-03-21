FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy the pyproject.toml and poetry.lock files into the container
COPY pyproject.toml poetry.lock /app/

# Install the dependencies
RUN poetry install --no-root --without dev --no-interaction

# Copy the rest of the application code
COPY . /app
RUN poetry install --no-interaction

# Expose the port the application will run on
EXPOSE 8000

# Start the application
CMD ["poetry", "run", "uvicorn", "prodsys_api:app", "--host",  "0.0.0.0", "--port", "8000"]