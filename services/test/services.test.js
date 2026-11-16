import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp, scenarios } from "../shared/app.js";
import { createPublisher } from "../shared/events.js";

async function fixture(t, service, options = {}) {
  const logs = [],
    events = [];
  const server = createApp(service, {
    env: { NODE_ENV: "development", ENABLE_FAULT_INJECTION: "true" },
    write: (line) => logs.push(JSON.parse(line)),
    publish: async (event) => events.push(event),
    ...options,
  }).listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  t.after(
    () =>
      new Promise((resolve) => {
        server.close(resolve);
        server.closeAllConnections();
      }),
  );
  const base = `http://127.0.0.1:${server.address().port}`;
  const request = async (
    path,
    body,
    method = body === undefined ? "GET" : "POST",
  ) => {
    const response = await fetch(base + path, {
      method,
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: response.status, body: await response.json() };
  };
  return { request, logs, events, base };
}
for (const service of ["user-service", "order-service", "payment-service"]) {
  test(`${service}: health, valid/invalid requests and retrieval`, async (t) => {
    const { request, logs, events } = await fixture(t, service);
    assert.equal((await request("/health")).body.data.status, "healthy");
    const route =
      service === "user-service"
        ? "/users"
        : service === "order-service"
          ? "/orders"
          : "/payments";
    const data =
      service === "user-service"
        ? {
            name: "Ada",
            email: "ada@example.test",
            password: "secret-password",
          }
        : service === "order-service"
          ? { user_id: "user-1", amount_cents: 10000 }
          : { order_id: "order-1", amount_cents: 10000 };
    const created = await request(route, data);
    assert.equal(created.status, 201);
    assert.equal(
      (await request(`${route}/${created.body.data.id}`)).status,
      200,
    );
    assert.equal((await request(`${route}/missing`)).status, 404);
    assert.equal((await request(route, {})).status, 400);
    if (service === "user-service")
      assert.equal((await request(route, data)).status, 409);
    if (service === "payment-service")
      assert.equal(created.body.data.total_cents, 10200);
    assert.equal((await request("/health")).status, 200);
    const raw = JSON.stringify(logs);
    assert.ok(
      !raw.includes("secret-password") && !raw.includes("ada@example.test"),
    );
    for (const field of [
      "timestamp",
      "service_name",
      "level",
      "request_id",
      "method",
      "path",
      "status_code",
      "duration_ms",
      "error_type",
      "error_message",
      "stack_trace",
    ])
      assert.ok(field in logs[0]);
    assert.ok(logs.every((log) => log.duration_ms >= 0));
    assert.ok(events.some((event) => event.http_status === 400));
  });
  test(`${service}: every controlled incident and recovery`, async (t) => {
    const { request, events, logs } = await fixture(t, service);
    const expected = [400, 500, 503, 504, 500, 500, 503, 500, 500, 200];
    for (const [index, scenario] of scenarios.entries()) {
      const result = await request(`/simulate/${scenario}`, {});
      assert.equal(result.status, expected[index], scenario);
      assert.equal(
        (await request("/health")).status,
        200,
        `recovery: ${scenario}`,
      );
    }
    for (let n = 0; n < 3; n++)
      assert.equal((await request("/simulate/repeated-500", {})).status, 500);
    const special =
      service === "user-service"
        ? ["authentication-error", 401]
        : service === "order-service"
          ? ["order-processing-error", 500]
          : ["payment-failure", 502];
    assert.equal(
      (await request(`/simulate/${special[0]}`, {})).status,
      special[1],
    );
    assert.equal((await request("/simulate/unknown", {})).status, 404);
    const event = events.find((event) => event.error_type === "InternalError");
    for (const field of [
      "event_id",
      "service_name",
      "timestamp",
      "severity",
      "error_type",
      "error_message",
      "stack_trace",
      "http_status",
      "request_id",
      "endpoint",
      "duration_ms",
    ])
      assert.ok(field in event);
    assert.match(event.event_id, /^[a-f0-9-]{36}$/);
    assert.ok(event.stack_trace);
    assert.ok(
      logs.some(
        (log) =>
          log.request_id === event.request_id &&
          log.status_code === event.http_status,
      ),
    );
    assert.ok(
      events.find((e) => e.error_type === "SlowDependency").duration_ms >= 50,
    );
  });
  test(`${service}: development-only gate`, async (t) => {
    for (const env of [
      {},
      { NODE_ENV: "production", ENABLE_FAULT_INJECTION: "true" },
      { NODE_ENV: "development" },
      { NODE_ENV: "test", ENABLE_FAULT_INJECTION: "true" },
    ]) {
      const { request } = await fixture(t, service, { env });
      for (const scenario of scenarios)
        assert.equal((await request(`/simulate/${scenario}`, {})).status, 403);
      assert.equal((await request("/health")).status, 200);
    }
  });
}
test("malformed/large bodies and unknown paths never leak input", async (t) => {
  const { base, logs, request } = await fixture(t, "payment-service");
  const malformed = await fetch(base + "/payments?token=secret-token", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: '{"password":"secret-password"',
  });
  assert.equal(malformed.status, 400);
  assert.equal(
    (await request("/payments", { value: "x".repeat(20000) })).status,
    413,
  );
  assert.equal(
    (await request("/secret-password?token=secret-token")).status,
    404,
  );
  assert.ok(!JSON.stringify(logs).includes("secret-password"));
  assert.ok(!JSON.stringify(logs).includes("secret-token"));
});
test("publisher rejects, times out and bounds concurrency without crashing", async () => {
  let failures = 0;
  const broken = createPublisher({
    transport: async () => {
      throw new Error("secret");
    },
    onFailure: () => failures++,
  });
  assert.equal(await broken({}), false);
  assert.equal(failures, 1);
  const blocked = createPublisher({
    transport: (_event, { signal }) =>
      new Promise((_, reject) =>
        signal.addEventListener("abort", () => reject(new Error("aborted"))),
      ),
    timeoutMs: 10,
    maxPending: 1,
  });
  const first = blocked({});
  assert.equal(await blocked({}), false);
  assert.equal(await first, false);
});
test("failed publication does not affect originating service", async (t) => {
  const { request } = await fixture(t, "order-service", {
    publish: async () => {
      throw new Error("offline");
    },
  });
  assert.equal((await request("/simulate/repeated-500", {})).status, 500);
  assert.equal((await request("/health")).status, 200);
});
test("real user → order → payment HTTP networking", async (t) => {
  const users = await fixture(t, "user-service");
  const orders = await fixture(t, "order-service", {
    env: { USER_SERVICE_URL: users.base },
  });
  const payments = await fixture(t, "payment-service", {
    env: { ORDER_SERVICE_URL: orders.base },
  });
  const user = await users.request("/users", {
    name: "Ada",
    email: "ada@example.test",
  });
  const order = await orders.request("/orders", {
    user_id: user.body.data.id,
    amount_cents: 10000,
  });
  assert.equal(order.status, 201);
  const payment = await payments.request("/payments", {
    order_id: order.body.data.id,
    amount_cents: 10000,
  });
  assert.equal(payment.status, 201);
  assert.equal(payment.body.data.total_cents, 10200);
  assert.equal(
    (
      await payments.request("/payments", {
        order_id: order.body.data.id,
        amount_cents: 1,
      })
    ).status,
    422,
  );
  assert.equal(
    (await orders.request("/orders", { user_id: "missing", amount_cents: 1 }))
      .status,
    422,
  );
});
test("downstream failure recovers on subsequent request", async (t) => {
  let broken = true;
  const { request } = await fixture(t, "order-service", {
    env: { USER_SERVICE_URL: "http://dependency.test" },
    fetcher: async () => {
      if (broken) throw new Error("connection refused");
      return { ok: true, status: 200 };
    },
  });
  assert.equal(
    (await request("/orders", { user_id: "user-1", amount_cents: 1 })).status,
    503,
  );
  broken = false;
  assert.equal(
    (await request("/orders", { user_id: "user-1", amount_cents: 1 })).status,
    201,
  );
});
test("memory operation concurrency is bounded", async (t) => {
  let release, started;
  const active = new Promise((resolve) => {
    started = resolve;
  });
  const { request } = await fixture(t, "payment-service", {
    wait: () =>
      new Promise((resolve) => {
        release = resolve;
        started();
      }),
  });
  const first = request("/simulate/bounded-memory", {});
  await active;
  const rejected = await Promise.all(
    Array.from({ length: 4 }, () => request("/simulate/bounded-memory", {})),
  );
  assert.ok(rejected.every((r) => r.status === 429));
  release();
  assert.equal((await first).status, 200);
  assert.equal((await request("/health")).status, 200);
});

test("default adapter publishes schema-conforming events to stdout", async (t) => {
  const { request, logs } = await fixture(t, "payment-service", {
    publish: undefined,
  });
  await request("/simulate/database-failure", {});
  const event = logs.find((log) => log.event === "incident").incident_event;
  const schema = JSON.parse(
    readFileSync(new URL("../incident-event.schema.json", import.meta.url)),
  );
  assert.deepEqual(Object.keys(event).sort(), schema.required.sort());
  for (const [key, rule] of Object.entries(schema.properties)) {
    const value = event[key];
    if (rule.enum) assert.ok(rule.enum.includes(value));
    if (rule.type === "string") assert.equal(typeof value, "string");
    if (rule.type === "integer") assert.ok(Number.isInteger(value));
    if (rule.type === "number") assert.equal(typeof value, "number");
    if (Array.isArray(rule.type))
      assert.ok(value === null || typeof value === "string");
    if (rule.minimum !== undefined) assert.ok(value >= rule.minimum);
    if (rule.maximum !== undefined) assert.ok(value <= rule.maximum);
    if (rule.format === "uuid")
      assert.match(
        value,
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
      );
    if (rule.format === "date-time")
      assert.ok(Number.isFinite(Date.parse(value)));
  }
});
test("uncooperative transports remain bounded after timeout", async () => {
  let calls = 0;
  const publish = createPublisher({
    transport: () => {
      calls++;
      return new Promise(() => {});
    },
    timeoutMs: 5,
    maxPending: 1,
  });
  assert.equal(await publish({}), false);
  assert.equal(await publish({}), false);
  assert.equal(calls, 1);
});

test("entry points reject unsafe fault settings and invalid ports", () => {
  for (const name of ["user", "order", "payment"]) {
    for (const env of [
      { NODE_ENV: "production", ENABLE_FAULT_INJECTION: "true" },
      { PORT: "invalid" },
    ]) {
      const child = spawnSync(
        process.execPath,
        [
          fileURLToPath(
            new URL(`../${name}-service/index.js`, import.meta.url),
          ),
        ],
        {
          env: {
            ...process.env,
            NODE_ENV: "production",
            ENABLE_FAULT_INJECTION: "false",
            PORT: "3001",
            ...env,
          },
          timeout: 5000,
          encoding: "utf8",
        },
      );
      assert.equal(child.status, 1);
      assert.match(child.stderr, /Fault injection requires|Invalid PORT/);
    }
  }
});
