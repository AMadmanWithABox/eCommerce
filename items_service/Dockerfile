FROM python:3.10-slim-buster

COPY ./requirements.txt /items-api/requirements.txt

EXPOSE 5000

WORKDIR /items-api

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY ./app.py /items-api/app.py
COPY ./data_generator.py ./data_generator.py

RUN python ./data_generator.py

CMD ["python", "app.py" ]