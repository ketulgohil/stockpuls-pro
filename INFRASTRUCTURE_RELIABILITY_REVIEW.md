# Technology and Infrastructure Review

## Recommendation

Keep the current technology stack for now; a framework rewrite is not needed to fix chart reliability. FastAPI, a static JavaScript frontend, Lightweight Charts, and Docker are a reasonable fit for this app. The chart issues identified so far point mainly to frontend lifecycle and request handling.

The larger reliability concern is the deployment and storage setup, especially as the app grows or supports multiple users.

## Current project setup

- Static single-page frontend with TradingView Lightweight Charts.
- FastAPI monolith serving API routes and WebSockets.
- In-memory caches.
- SQLite and JSON files stored under `data/`.
- Fly.io configuration uses one shared-CPU machine with 512 MB memory and no configured HTTP health check.
- Fly config sets `auto_stop_machines = false` and `min_machines_running = 0`; with autostop disabled, the minimum does not provide redundancy.
- Live prices use WebSockets. Connections can close during proxy restarts, machine stops, deployments, or network interruptions, so the client needs reconnect and resubscribe behavior. See [Fly.io WebSocket guidance](https://fly.io/learn/websockets-workers-cron/).

## Infrastructure recommendations

### 1. Protect user data

SQLite and JSON files in the app's local `data/` directory are a risk if those files must persist across deployments or machine replacement. Fly Volumes are local to a machine, which also complicates sharing state across multiple machines. Before scaling out, move user-owned portfolio, watchlist, alert, and settings data to managed PostgreSQL. See [Fly.io storage overview](https://fly.io/docs/volumes/overview/).

Keep SQLite for local development or single-instance experiments if convenient. For production with multiple users or machines, use a shared database and a migration process.

### 2. Add health checks and deployment safeguards

Add a lightweight readiness endpoint and configure Fly health checks to use it. The check should verify that the app can serve requests without depending on slow external market-data providers. Health checks help detect an unhealthy app, but they do not replace redundancy or monitoring.

### 3. Make the WebSocket path resilient

- Implement and verify client reconnect with backoff.
- Resubscribe after reconnect.
- Display clear stale and disconnected states.
- Make subscriptions idempotent.
- Ensure an old socket cannot overwrite data after the user changes symbols.

### 4. Separate market polling from web request processes

The app includes background market polling and WebSocket serving. If more web machines are added, each process may run its own in-memory engine and cache, potentially creating duplicate provider polling and inconsistent state. A separate worker process and shared message/cache layer can address this as the app grows. This is a scaling step, not a prerequisite for fixing the chart bug.

### 5. Measure resource use before resizing

The current 512 MB machine may be tight for a Python app using pandas, many API routes, and live connections, but the config alone does not show whether it is currently insufficient. Track memory, restarts, response latency, and WebSocket connection counts under realistic use before choosing a larger size. Set concurrency limits based on measurements; Fly recommends treating WebSocket connections differently from ordinary short HTTP requests. See [Fly.io WebSocket guidance](https://fly.io/learn/websockets-workers-cron/).

### 6. Treat caches as disposable

The current cache is process-local. That is fine as an optimization for one process, but it will not be shared across multiple machines and will be lost on restart. Do not rely on it as the source of truth for quotes, alerts, or user data. If shared caching becomes necessary, add a shared cache such as Redis.

## Suggested path

1. Fix chart initialization, request ordering, and stale-response handling in the current frontend.
2. Add app health checks, logging, and basic resource monitoring.
3. Verify reconnect and resubscribe behavior for live WebSockets.
4. Confirm how production data files persist on Fly and add backups.
5. Move user-owned state to managed PostgreSQL before relying on multiple app machines.
6. Separate background polling into a worker when duplicate polling, resource contention, or deployment behavior becomes a real issue.

## Conclusion

The current stack is suitable. The next investment should be reliability work and durable shared storage, not a technology rewrite.
