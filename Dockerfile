FROM python:3.9-slim
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask flask-cors requests yt-dlp
# EXPOSEは書かずに、Railwayに任せます
CMD ["python", "app.py"]
