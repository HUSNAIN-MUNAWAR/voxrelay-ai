# Deployment

For a non-demo deployment, use PostgreSQL, Redis, managed object storage, a secret manager, TLS termination, scoped CORS origins, secure cookie/session policy where applicable, structured log shipping and explicit migrations.

```mermaid
flowchart LR
  LB[TLS load balancer] --> Web[Next.js]
  LB --> API[FastAPI replicas]
  API --> PG[(PostgreSQL)]
  API --> Redis[(Redis)]
  API --> Obj[S3-compatible storage]
  API --> Adapters[Credentialed provider adapters]
```

The supplied Compose configuration is development reference infrastructure, not a high-availability deployment topology.
