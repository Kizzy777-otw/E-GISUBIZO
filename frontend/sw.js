/* Minimal app-shell cache and retry hook for tickets saved in IndexedDB. */
"use strict";

const CACHE_NAME = "egisubizo-shell-v1";
const APP_ASSETS = [
  "/",
  "/index.html",
  "/technician.html",
  "/admin.html",
  "/styles.css",
  "/app.js",
  "/technician.js",
  "/admin.js",
  "/manifest.webmanifest",
  "/icon.svg",
];
const DB_NAME = "egisubizo-local";
const DB_VERSION = 1;
const TICKET_STORE = "tickets";

self.addEventListener("install", (event) => {
  // Precache the small local app shell so first navigation works without a network.
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  // Retire old app-shell versions after the replacement is installed.
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("egisubizo-shell-") && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);
  if (event.request.method !== "GET" || requestUrl.origin !== self.location.origin || requestUrl.pathname.startsWith("/api/")) return;
  // API responses are always network-only; offline records live in IndexedDB instead.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {
      if (response.ok && response.type === "basic") {
        const copy = response.clone();
        void caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      }
      return response;
    })),
  );
});

self.addEventListener("sync", (event) => {
  if (event.tag === "ticket-sync") event.waitUntil(syncTickets());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SYNC_TICKETS") event.waitUntil(syncTickets());
});

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(TICKET_STORE)) db.createObjectStore(TICKET_STORE, { keyPath: "client_ticket_id" });
      if (!db.objectStoreNames.contains("trees")) db.createObjectStore("trees", { keyPath: "slug" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open ticket queue."));
  });
}

function readQueued(db) {
  return new Promise((resolve, reject) => {
    const request = db.transaction(TICKET_STORE, "readonly").objectStore(TICKET_STORE).getAll();
    request.onsuccess = () => resolve(request.result.filter((ticket) => ticket.state === "queued"));
    request.onerror = () => reject(request.error || new Error("Could not read ticket queue."));
  });
}

function updateTicket(db, ticketId, update) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(TICKET_STORE, "readwrite");
    const store = transaction.objectStore(TICKET_STORE);
    if (update === null) store.delete(ticketId);
    else {
      const request = store.get(ticketId);
      request.onsuccess = () => {
        if (request.result) store.put({ ...request.result, ...update });
      };
    }
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error || new Error("Could not update ticket queue."));
  });
}

async function syncTickets() {
  if (!self.navigator.onLine) return;
  const db = await openDatabase();
  try {
    const queued = await readQueued(db);
    if (!queued.length) return;
    const response = await fetch("/api/v1/tickets/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ tickets: queued.map(({ state, created_at, ...ticket }) => ticket) }),
    });
    if (!response.ok) throw new Error(`Ticket sync failed (${response.status}).`);
    const result = await response.json();
    // Keep failed/rejected records for the foreground UI; delete only server acknowledgements.
    for (const item of result.results || []) {
      if (item.result === "synced" || item.result === "already_synced") {
        await updateTicket(db, item.client_ticket_id, null);
      } else {
        await updateTicket(db, item.client_ticket_id, { state: "rejected", sync_error: item.message || "Ticket rejected." });
      }
    }
  } finally {
    db.close();
  }
}
