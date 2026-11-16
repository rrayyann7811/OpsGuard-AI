import express from "express";
import { randomUUID } from "node:crypto";
import { performance } from "node:perf_hooks";
import { createPublisher, incidentEvent, httpTransport } from "./events.js";

export class ServiceError extends Error {
  constructor(status, type, message) {
    super(message);
    this.status = status;
    this.type = type;
  }
}
const fail = (status, type, message) => {
  throw new ServiceError(status, type, message);
};
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const positive = (n) => Number.isSafeInteger(n) && n > 0 && n <= 100000000;
const validId = (id) =>
  typeof id === "string" && /^[a-zA-Z0-9-]{1,64}$/.test(id);
const text = (value) =>
  typeof value === "string" && value.trim().length > 0 && value.length <= 100;
export const scenarios = [
  "missing-payment-amount",
  "null-access",
  "database-failure",
  "request-timeout",
  "invalid-configuration",
  "calculation-regression",
  "slow-downstream",
  "repeated-500",
  "faulty-commit",
  "bounded-memory",
];

export function createApp(
  service,
  {
    env = process.env,
    write = (line) => process.stdout.write(line + "\n"),
    publish,
    fetcher = fetch,
    wait = delay,
  } = {},
) {
  if (!["user-service", "order-service", "payment-service"].includes(service))
    throw new Error("Unknown service");
  const app = express();
  app.disable("x-powered-by");
  const records = new Map();
  const log = (record) => {
    try {
      write(JSON.stringify(record));
    } catch {
      /* A broken log sink must not crash requests. */
    }
  };
  const publisher =
    publish ??
    (async (event) =>
      log({
        timestamp: event.timestamp,
        service_name: service,
        level: event.severity === "error" ? "error" : "warn",
        request_id: event.request_id,
        method: null,
        path: event.endpoint,
        status_code: event.http_status,
        duration_ms: event.duration_ms,
        error_type: event.error_type,
        error_message: event.error_message,
        stack_trace: event.stack_trace,
        event: "incident",
        incident_event: event,
      }));
  const remote = env.INCIDENT_INGESTION_URL
    ? httpTransport({
        url: env.INCIDENT_INGESTION_URL,
        token: env.INCIDENT_WEBHOOK_TOKEN,
      })
    : null;
  const sendEvent = createPublisher({
    timeoutMs: 2000,
    transport: async (event, options) => {
      await publisher(event, options);
      if (remote) await remote(event, options);
    },
    onFailure: () =>
      log({
        timestamp: new Date().toISOString(),
        service_name: service,
        level: "error",
        request_id: null,
        method: null,
        path: null,
        status_code: null,
        duration_ms: null,
        error_type: "PublicationFailure",
        error_message: "Incident publication failed",
        stack_trace: null,
      }),
  });
  app.use((req, res, next) => {
    req.id = randomUUID(); // Do not trust or log caller-controlled identifiers.
    res.set("X-Request-ID", req.id);
    const started = performance.now();
    res.on("finish", () => {
      const duration = Math.round((performance.now() - started) * 100) / 100;
      // Only route templates are logged: query strings, IDs and bodies may contain secrets.
      const path = req.route?.path ?? "/unmatched";
      log({
        timestamp: new Date().toISOString(),
        service_name: service,
        level:
          res.statusCode >= 500
            ? "error"
            : res.statusCode >= 400
              ? "warn"
              : "info",
        request_id: req.id,
        method: req.method,
        path,
        status_code: res.statusCode,
        duration_ms: duration,
        error_type: res.locals.error?.type ?? null,
        error_message: res.locals.error?.message ?? null,
        stack_trace: res.locals.error?.stack ?? null,
      });
      if (res.locals.error)
        void sendEvent(
          incidentEvent(
            service,
            { id: req.id, path },
            res.locals.error,
            res.statusCode,
            duration,
          ),
        );
    });
    next();
  });
  app.use(express.json({ limit: "16kb", strict: true }));
  app.get("/health", (_req, res) =>
    res.json({ success: true, data: { service, status: "healthy" } }),
  );
  const ok = (res, data, status = 200) =>
    res.status(status).json({ success: true, data });
  const save = (data, res) => {
    if (records.size >= 1000)
      fail(503, "CapacityExceeded", "Local record capacity reached");
    const record = { id: randomUUID(), ...data };
    records.set(record.id, record);
    ok(res, record, 201);
  };
  const retrieve = (req, res) => {
    if (!validId(req.params.id))
      fail(400, "ValidationError", "Invalid record ID");
    const record = records.get(req.params.id);
    if (!record) fail(404, "NotFound", "Record not found");
    ok(res, record);
  };
  if (service === "user-service") {
    app.get("/users", (_req, res) => ok(res, [...records.values()]));
    app.get("/users/:id", retrieve);
    app.post("/users", (req, res) => {
      const { name, email } = req.body ?? {};
      if (
        !text(name) ||
        typeof email !== "string" ||
        email.length > 254 ||
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
      )
        fail(400, "ValidationError", "Name and valid email are required");
      if (
        [...records.values()].some((user) => user.email === email.toLowerCase())
      )
        fail(409, "DuplicateUser", "User already registered");
      save({ name: name.trim(), email: email.toLowerCase() }, res);
    });
  }
  if (service === "order-service") {
    app.get("/orders/:id", retrieve);
    app.post("/orders", async (req, res) => {
      const { user_id, amount_cents } = req.body ?? {};
      if (!validId(user_id) || !positive(amount_cents))
        fail(
          400,
          "ValidationError",
          "Valid user_id and positive integer amount_cents are required",
        );
      if (env.USER_SERVICE_URL) {
        let response;
        try {
          response = await fetcher(
            new URL(
              `/users/${encodeURIComponent(user_id)}`,
              env.USER_SERVICE_URL,
            ),
            { signal: AbortSignal.timeout(1000) },
          );
        } catch {
          fail(503, "DependencyUnavailable", "User service unavailable");
        }
        if (response.status === 404)
          fail(422, "UnknownUser", "User does not exist");
        if (!response.ok)
          fail(503, "DependencyUnavailable", "User service rejected lookup");
      }
      save({ user_id, amount_cents, status: "created" }, res);
    });
  }
  const calculate = (amount, regression = false) => {
    if (!positive(amount))
      fail(400, "ValidationError", "Positive integer amount_cents is required");
    const expected = amount + Math.round(amount * 0.02);
    const actual = regression ? amount - Math.round(amount * 0.02) : expected;
    if (actual !== expected)
      fail(
        500,
        "CalculationRegression",
        "Payment total violated fee invariant",
      );
    return actual;
  };
  if (service === "payment-service") {
    app.get("/payments/:id", retrieve);
    app.post("/payments", async (req, res) => {
      const { order_id, amount_cents } = req.body ?? {};
      const total_cents = calculate(amount_cents);
      if (!validId(order_id))
        fail(400, "ValidationError", "Valid order_id is required");
      if (env.ORDER_SERVICE_URL) {
        let response;
        try {
          response = await fetcher(
            new URL(
              `/orders/${encodeURIComponent(order_id)}`,
              env.ORDER_SERVICE_URL,
            ),
            { signal: AbortSignal.timeout(1000) },
          );
        } catch {
          fail(503, "DependencyUnavailable", "Order service unavailable");
        }
        if (response.status === 404)
          fail(422, "UnknownOrder", "Order does not exist");
        if (!response.ok)
          fail(503, "DependencyUnavailable", "Order service rejected lookup");
        const order = await response.json();
        if (order.data?.amount_cents !== amount_cents)
          fail(422, "AmountMismatch", "Payment amount does not match order");
      }
      save({ order_id, amount_cents, total_cents, status: "processed" }, res);
    });
  }
  let memoryBusy = false;
  app.post("/simulate/:scenario", async (req, res) => {
    if (env.NODE_ENV !== "development" || env.ENABLE_FAULT_INJECTION !== "true")
      fail(
        403,
        "FaultInjectionDisabled",
        "Fault injection requires explicit local development configuration",
      );
    const scenario = req.params.scenario;
    if (scenario === "authentication-error" && service === "user-service")
      fail(401, "AuthenticationError", "Simulated credentials rejected");
    if (scenario === "order-processing-error" && service === "order-service")
      fail(500, "OrderProcessingError", "Simulated order processing failure");
    if (scenario === "payment-failure" && service === "payment-service")
      fail(502, "PaymentFailure", "Simulated payment processor rejection");
    if (!scenarios.includes(scenario))
      fail(404, "UnknownScenario", "Unknown incident scenario");
    switch (scenario) {
      case "missing-payment-amount":
        calculate(undefined);
        break;
      case "null-access": {
        const customer = null;
        customer.profile;
        break;
      }
      case "database-failure":
        fail(
          503,
          "DatabaseConnectionError",
          "Simulated database connection refused",
        );
        break;
      case "request-timeout": {
        // A real abortable operation, without leaving a background timer behind.
        const { setTimeout } = await import("node:timers/promises");
        try {
          await setTimeout(500, null, { signal: AbortSignal.timeout(30) });
        } catch {
          fail(504, "RequestTimeout", "Operation exceeded 30ms deadline");
        }
        break;
      }
      case "invalid-configuration": {
        const config = { feeRate: "invalid" };
        if (!Number.isFinite(Number(config.feeRate)))
          fail(
            500,
            "ConfigurationError",
            "Payment fee configuration is invalid",
          );
        break;
      }
      case "calculation-regression":
        calculate(10000, true);
        break;
      case "slow-downstream":
        await wait(60);
        fail(
          503,
          "SlowDependency",
          "Simulated downstream exceeded 50ms latency budget",
        );
        break;
      case "repeated-500":
        fail(500, "RepeatedServerError", "Controlled repeatable failure");
        break;
      case "faulty-commit": {
        // A versioned fixture, never a mutation of the actual Git repository.
        const { total } = await import("../fixtures/faulty-commit.js");
        if (total(10000) !== 10200)
          fail(
            500,
            "FaultyCommitRegression",
            "Fixture revision regression-fee-v1 failed total invariant",
          );
        break;
      }
      case "bounded-memory": {
        if (memoryBusy)
          fail(429, "SimulationBusy", "Memory simulation already running");
        memoryBusy = true;
        try {
          const buffer = Buffer.alloc(4 * 1024 * 1024, 1);
          await wait(20);
          ok(res, {
            allocated_bytes: buffer.length,
            checksum: buffer[0] + buffer[buffer.length - 1],
          });
        } finally {
          memoryBusy = false;
        }
        return;
      }
    }
  });
  app.use((_req, _res, next) =>
    next(new ServiceError(404, "NotFound", "Endpoint not found")),
  );
  app.use((error, req, res, _next) => {
    // Never echo parser errors or external exception messages, which may contain input.
    const safe =
      error instanceof ServiceError
        ? error
        : new ServiceError(
            error.type === "entity.too.large"
              ? 413
              : error instanceof SyntaxError
                ? 400
                : 500,
            error instanceof SyntaxError
              ? "InvalidJson"
              : error.type === "entity.too.large"
                ? "PayloadTooLarge"
                : "InternalError",
            error instanceof SyntaxError
              ? "Malformed JSON body"
              : "Request could not be completed",
          );
    const stack =
      safe.status >= 500
        ? [safe.message, ...(error.stack?.split("\n").slice(1) ?? [])].join(
            "\n",
          )
        : null;
    res.locals.error = { type: safe.type, message: safe.message, stack };
    res.status(safe.status).json({
      success: false,
      error: { type: safe.type, message: safe.message },
      request_id: req.id,
    });
  });
  return app;
}
