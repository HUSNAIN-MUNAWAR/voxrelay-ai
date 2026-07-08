# Provider operations

Provider records report provider type, status, credential state, environment, last health check, last success, failures, retry policy and safe settings metadata. Status values distinguish `not_configured`, `demo_provider`, `connected`, `degraded`, `failing` and `disabled`.

The Provider Operations Center can run only a local health-test simulation. It does not make an external credentialed call. Job records support idempotency, retry metadata, failure reason, dead-letter-style state and redacted payload previews.
