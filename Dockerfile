ARG APP_VERSION=0.4.2

FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the poetry files into the container
COPY pyproject.toml poetry.lock /app/

# Install dependencies using Poetry
RUN pip install prodsys==0.4.2



COPY . /app

EXPOSE 8000

CMD ["python", "app.py", "fastapi=linux"]