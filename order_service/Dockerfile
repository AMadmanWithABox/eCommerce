FROM python:3.10-slim-buster

COPY ./requirements.txt /order-api/requirements.txt

EXPOSE 5002

WORKDIR /order-api

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY ./app.py /order-api/app.py

CMD ["python", "app.py" ]