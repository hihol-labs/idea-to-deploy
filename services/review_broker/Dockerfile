FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/itd \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/itd

COPY services/review_broker/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

COPY --chown=65532:65532 services /opt/itd/services
COPY --chown=65532:65532 skills/_shared /opt/itd/skills/_shared

USER 65532:65532
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request; value=json.load(urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)); assert value['status']=='ok'"]

ENTRYPOINT ["python", "-m", "services.review_broker"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
