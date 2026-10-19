FROM python:3.13-alpine3.22

RUN apk add --no-cache openssl

WORKDIR /app
COPY demo/secure-mcp/requirements.txt /tmp/secure-mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/secure-mcp-requirements.txt

COPY demo/secure-mcp/gateway/openssl-pqc.cnf /etc/ssl/openssl-pqc.cnf
COPY demo/secure-mcp/coordinator/client.py /app/coordinator.py

ENV OPENSSL_CONF=/etc/ssl/openssl-pqc.cnf \
    GUARD_MCP_URL=https://guard-ai.demo:8443/mcp \
    GUARD_MCP_TOKEN_FILE=/run/guard-ai/tokens/coordinator.jwt \
    GUARD_MCP_CA_FILE=/run/guard-ai/certs/interop/ca.crt \
    GUARD_MCP_CLIENT_CERT=/run/guard-ai/certs/interop/client.crt \
    GUARD_MCP_CLIENT_KEY=/run/guard-ai/certs/interop/client.key

ENTRYPOINT ["python", "/app/coordinator.py"]
