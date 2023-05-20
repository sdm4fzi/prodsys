FROM python:3.11
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app.py /code/app.py
COPY ./conf /code/conf
COPY ./examples /code/examples
COPY ./prodsys /code/prodsys
COPY ./app /code/app

EXPOSE 8000

CMD ["python", "app.py", "fastapi=linux"]