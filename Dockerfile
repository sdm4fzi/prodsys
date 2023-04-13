FROM python:3.11
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./fastapi_app.py /code/fastapi_app.py
COPY ./conf /code/conf
COPY ./examples /code/examples
COPY ./prodsim /code/prodsim

EXPOSE 8000

CMD ["python", "fastapi_app.py", "fastapi=linux"]