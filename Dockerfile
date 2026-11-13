FROM python:3.12-slim
WORKDIR /app
COPY tools/ tools/
COPY laws/ laws/
COPY store/ store/
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
EXPOSE 8080
# axhub 가 PORT 를 넣어 주면 0.0.0.0:PORT 로 열린다 (tools/server.py bind_address)
CMD ["python", "tools/server.py"]
