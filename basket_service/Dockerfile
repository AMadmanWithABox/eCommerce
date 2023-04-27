FROM python:3.10-slim-buster

COPY ./requirements.txt /basket-api/requirements.txt

EXPOSE 5001

WORKDIR /basket-api

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY ./app.py /basket-api/app.py

CMD ["python", "app.py" ]