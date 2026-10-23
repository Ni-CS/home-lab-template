FROM python:3.12-slim-bookworm AS build
WORKDIR /src
COPY apps/portal/manage.py apps/portal/manage.py
COPY apps/portal/web apps/portal/web
COPY catalog/services.json catalog/services.json
COPY catalog/portal-ui.json catalog/portal-ui.json
RUN python apps/portal/manage.py build --output-dir /out

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=build /out /app/public
COPY apps/portal/manage.py /app/manage.py
COPY apps/portal/config.example.json /app/config.example.json
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
CMD ["python", "manage.py", "serve", "--directory", "/app/public", "--config", "/config/portal.json", "--bind", "0.0.0.0", "--port", "8080"]
