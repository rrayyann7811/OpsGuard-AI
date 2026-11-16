import { createApp } from "../shared/app.js";
const port = Number(process.env.PORT ?? 3001);
if (!Number.isInteger(port) || port < 1 || port > 65535)
  throw new Error("Invalid PORT");
if (
  process.env.ENABLE_FAULT_INJECTION === "true" &&
  process.env.NODE_ENV !== "development"
)
  throw new Error("Fault injection requires NODE_ENV=development");
const server = createApp("user-service").listen(
  port,
  process.env.HOST ?? "127.0.0.1",
);
server.requestTimeout = 5000;
server.headersTimeout = 5000;
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 5000).unref();
  });
