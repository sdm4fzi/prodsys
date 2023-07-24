FROM python:3.11
RUN pip install "poetry==1.4.2"


WORKDIR /code
COPY . /code

RUN poetry install --no-interaction --no-ansi

EXPOSE 8000

CMD ["python", "app.py", "fastapi=linux"]