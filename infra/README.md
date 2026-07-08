# Infrastructure notes

`docker-compose.yml` is intentionally a portable reference stack: PostgreSQL, Redis, API worker, API gateway, and Next.js web application.

For production, split the services, use managed PostgreSQL/Redis, terminate TLS at a load balancer, store secrets in a secret manager, restrict network egress, add object storage for recordings, and send observability data to your approved platform.
