FROM python:3.11-slim

WORKDIR /app

COPY main.py ./main.py
COPY frontend/ ./frontend/
COPY data/demo_data.json ./data/demo_data.json

RUN pip install --no-cache-dir fastapi uvicorn[standard]

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
