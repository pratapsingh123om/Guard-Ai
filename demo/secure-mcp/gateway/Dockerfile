FROM python:3.13-alpine3.22

RUN apk add --no-cache openssl

WORKDIR /app

COPY demo/secure-mcp/requirements.txt /tmp/secure-mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/secure-mcp-requirements.txt

RUN apk add --no-cache nginx

COPY backend ./backend

COPY demo/secure-mcp/gateway/nginx.conf /etc/nginx/nginx.conf
COPY demo/secure-mcp/gateway/openssl-pqc.cnf /etc/ssl/openssl-pqc.cnf
COPY demo/secure-mcp/gateway/entrypoint.sh /usr/local/bin/guard-ai-entrypoint

RUN chmod 0555 /usr/local/bin/guard-ai-entrypoint

ENV OPENSSL_CONF=/etc/ssl/openssl-pqc.cnf \
    GUARD_MCP_ISSUER_URL=https://issuer.guard-ai.demo \
    GUARD_MCP_RESOURCE_URL=https://guard-ai.demo:8443/mcp \
    GUARD_MCP_JWT_PUBLIC_KEY_FILE=/run/guard-ai/tokens/issuer-public.pem \
    GUARD_MCP_ALLOWED_HOSTS=guard-ai.demo \
    GUARD_MCP_ALLOWED_ORIGINS=https://guard-ai.demo \
    GUARD_MCP_TLS_VERSION=TLSv1.3 \
    GUARD_MCP_TLS_GROUP=X25519MLKEM768

EXPOSE 8443 9443

ENTRYPOINT ["/usr/local/bin/guard-ai-entrypoint"]
