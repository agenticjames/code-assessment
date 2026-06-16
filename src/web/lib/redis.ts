/**
 * Shared ioredis connection (server-only). Queue (XADD) + cancel flag + trace keys live here.
 * A global singleton survives dev HMR so we don't leak connections on every reload.
 */
import "server-only";

import Redis from "ioredis";

import { env } from "@/lib/env";

declare global {
  var __biggyRedis: Redis | undefined;
}

export const redis =
  global.__biggyRedis ?? new Redis(env.REDIS_URL, { maxRetriesPerRequest: null });

if (process.env.NODE_ENV !== "production") global.__biggyRedis = redis;

export const JOBS_STREAM = "biggy:jobs";
export const cancelKey = (id: string) => `cancel:${id}`;
export const traceKey = (id: string) => `trace:${id}`;
