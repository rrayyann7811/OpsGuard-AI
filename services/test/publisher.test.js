import { test } from "node:test";
import assert from "node:assert/strict";
import {
  httpTransport,
  createPublisher,
  incidentEvent,
} from "../shared/events.js";

const event = incidentEvent(
  "payment-service",
  { id: crypto.randomUUID(), path: "/payments" },
  {
    type: "PaymentFailure",
    message: "Processor rejected payment",
    stack: null,
  },
  502,
  1,
);
const config = {
  url: "http://backend.test/api/incidents/events",
  token: "server-only-secret",
};
test("successful authenticated publication uses unchanged event contract", async () => {
  let calls = 0;
  const transport = httpTransport({
    ...config,
    fetcher: async (url, options) => {
      calls++;
      assert.equal(url.pathname, "/api/incidents/events");
      assert.equal(options.headers.authorization, "Bearer server-only-secret");
      assert.deepEqual(JSON.parse(options.body), event);
      assert.equal(options.redirect, "error");
      return new Response("{}", { status: 200 });
    },
  });
  assert.equal(
    await createPublisher({ transport, timeoutMs: 2000 })(event),
    true,
  );
  assert.equal(calls, 1);
});
test("transient failures retry at most three times with same event id", async () => {
  const payloads = [];
  const transport = httpTransport({
    ...config,
    fetcher: async (_url, options) => {
      payloads.push(options.body);
      return new Response("{}", { status: payloads.length < 3 ? 503 : 200 });
    },
  });
  assert.equal(
    await createPublisher({ transport, timeoutMs: 2000 })(event),
    true,
  );
  assert.equal(payloads.length, 3);
  assert.equal(new Set(payloads).size, 1);
});
test("permanent rejection does not retry or reveal credentials", async () => {
  let calls = 0;
  const transport = httpTransport({
    ...config,
    fetcher: async () => {
      calls++;
      return new Response("{}", { status: 401 });
    },
  });
  await assert.rejects(
    transport(event, { signal: new AbortController().signal }),
    (error) => !error.message.includes(config.token),
  );
  assert.equal(calls, 1);
});
test("backend outage is bounded and returns publication failure", async () => {
  let calls = 0;
  const transport = httpTransport({
    ...config,
    fetcher: async () => {
      calls++;
      throw new Error("offline");
    },
  });
  assert.equal(
    await createPublisher({ transport, timeoutMs: 2000 })(event),
    false,
  );
  assert.equal(calls, 3);
});
test("backend timeout aborts requests and retry budget", async () => {
  let calls = 0;
  const transport = httpTransport({
    ...config,
    attemptTimeoutMs: 5,
    fetcher: async (_url, { signal }) => {
      calls++;
      return new Promise((_, reject) =>
        signal.addEventListener("abort", () => reject(new Error("timeout")), {
          once: true,
        }),
      );
    },
  });
  assert.equal(
    await createPublisher({ transport, timeoutMs: 40 })(event),
    false,
  );
  assert.equal(calls, 1);
});
test("unsafe transport configuration is rejected", () => {
  assert.throws(() =>
    httpTransport({ url: "file:///tmp/event", token: "secret" }),
  );
  assert.throws(() => httpTransport({ url: config.url, token: "" }));
  assert.throws(() =>
    httpTransport({
      url: "http://user:password@backend.test",
      token: "secret",
    }),
  );
});

test("actual producer payload validates against the v1 JSON Schema", async () => {
  const { readFileSync } = await import("node:fs");
  const { default: Ajv } = await import("ajv/dist/2020.js");
  const { default: addFormats } = await import("ajv-formats");
  const ajv = new Ajv();
  addFormats(ajv);
  const validate = ajv.compile(
    JSON.parse(
      readFileSync(new URL("../incident-event.schema.json", import.meta.url)),
    ),
  );
  assert.equal(validate(event), true, JSON.stringify(validate.errors));
  assert.equal(validate({ ...event, event_id: "bad" }), false);
  assert.equal(validate({ ...event, extra: "rejected" }), false);
});
