FROM python:3.10-slim

# Render requiere este puerto para sus health checks
EXPOSE 10000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
