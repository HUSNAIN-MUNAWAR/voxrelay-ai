# Calendar and booking

The local deterministic calendar provider persists appointments and booking attempts. It validates end time, tenant ownership and assignee overlap; conflicts return `409` and create a failed booking attempt. Reschedule/cancel endpoints create audit events.

The production-facing design leaves boundaries for Google Calendar-compatible, Microsoft 365-compatible and CalDAV implementations. No real external calendar synchronization occurs in demo mode.
