FROM python:3.10-slim-buster

WORKDIR /data_generator

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY data_generator.py .

CMD ["python", "./data_generator.py"]