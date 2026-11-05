/* Citizen portal: data-driven diagnostics, offline tree cache, and queued ticket sync. */
(() => {
  "use strict";

  const DB_NAME = "egisubizo-local";
  const DB_VERSION = 1;
  const TICKET_STORE = "tickets";
  const TREE_STORE = "trees";
  const API = "/api/v1";
  const form = document.getElementById("hardware-form");
  const message = document.getElementById("app-message");
  const hardwarePanel = document.getElementById("hardware-panel");
  const diagnosticPanel = document.getElementById("diagnostic-panel");
  const diagnosticContent = document.getElementById("diagnostic-content");
  const connectionStatus = document.getElementById("connection-status");
  const queueStatus = document.getElementById("queue-status");
  const modelLabel = document.getElementById("model-label");
  let database;
  let selectedUnit;
  let activeTree;
  let currentNodeId;
  let traversal = [];

  function openDatabase() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) {
        reject(new Error("This browser does not support offline storage. Please use a recent mobile browser."));
        return;
      }
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        // Keep tree snapshots and unsent tickets in separate stores for offline reads.
        const db = request.result;
        if (!db.objectStoreNames.contains(TICKET_STORE)) {
          db.createObjectStore(TICKET_STORE, { keyPath: "client_ticket_id" });
        }
        if (!db.objectStoreNames.contains(TREE_STORE)) {
          db.createObjectStore(TREE_STORE, { keyPath: "slug" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Could not open offline storage."));
    });
  }

  function transact(storeName, mode, action) {
    return new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, mode);
      const request = action(transaction.objectStore(storeName));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Offline storage operation failed."));
      transaction.onabort = () => reject(transaction.error || new Error("Offline storage transaction was aborted."));
    });
  }

  function showMessage(text, kind = "info") {
    message.textContent = text;
    message.className = `notice notice-${kind}`;
    message.hidden = false;
  }

  function setConnection() {
    const online = navigator.onLine;
    connectionStatus.classList.toggle("offline", !online);
    connectionStatus.querySelector("span:last-child").textContent = online ? "Internet irahari" : "Nta internet · Offline";
  }

  async function getAll(storeName) {
    return transact(storeName, "readonly", (store) => store.getAll());
  }

  async function getCachedUnit(hardwareId, modelType) {
    const entries = await getAll(TREE_STORE);
    const cachedUnits = entries.find((entry) => entry.kind === "validated-hardware")?.units || [];
    return cachedUnits.find((unit) => unit.hardware_id === hardwareId && unit.model_type === modelType);
  }

  async function rememberUnit(unit) {
    const entries = await getAll(TREE_STORE);
    const record = entries.find((entry) => entry.kind === "validated-hardware") || {
      slug: "validated-hardware",
      kind: "validated-hardware",
      units: [],
    };
    // Replace stale validation data for this unit instead of creating duplicates.
    record.units = record.units.filter((saved) => saved.hardware_id !== unit.hardware_id);
    record.units.push(unit);
    await transact(TREE_STORE, "readwrite", (store) => store.put(record));
  }

  async function refreshTrees() {
    if (!navigator.onLine) return;
    const response = await fetch(`${API}/diagnostic-trees`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Decision trees could not be refreshed (${response.status}).`);
    const trees = await response.json();
    const transaction = database.transaction(TREE_STORE, "readwrite");
    const store = transaction.objectStore(TREE_STORE);
    for (const tree of trees) store.put({ ...tree, kind: "diagnostic-tree" });
    await new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error("Could not save decision trees offline."));
      transaction.onabort = () => reject(transaction.error || new Error("Saving decision trees offline was cancelled."));
    });
  }

  async function getTree(modelType) {
    const cached = (await getAll(TREE_STORE)).filter((entry) => entry.kind === "diagnostic-tree");
    return cached.find((tree) => tree.appliance_type === modelType);
  }

  async function updateQueueCount() {
    const tickets = await getAll(TICKET_STORE);
    const pending = tickets.filter((ticket) => ticket.state !== "synced").length;
    queueStatus.textContent = `Tike zibitswe kuri telefoni: ${pending}`;
  }

  function safeText(element, text) {
    element.textContent = text || "";
    return element;
  }

  function renderQuestion(node) {
    const wrapper = document.createElement("div");
    wrapper.className = "question-view";
    const count = document.createElement("p");
    count.className = "eyebrow";
    count.textContent = `INTAMBWE ${Math.min(traversal.length + 1, 3)} KURI 3 · STEP ${Math.min(traversal.length + 1, 3)} OF 3`;
    const icon = document.createElement("div");
    icon.className = "diagnostic-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = node.icon || "❓";
    const title = document.createElement("h2");
    safeText(title, node.question);
    const translation = document.createElement("p");
    translation.className = "translation";
    safeText(translation, node.translation);
    const choices = document.createElement("div");
    choices.className = "answer-list";
    for (const answer of node.answers || []) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "answer-button";
      button.textContent = answer.label;
      button.addEventListener("click", () => {
        void selectAnswer(node, answer).catch((error) => {
          currentNodeId = traversal.pop()?.node_id || currentNodeId;
          showMessage(error.message || "Igenzura ntiryabitswe. Ongera ugerageze.", "error");
        });
      });
      choices.append(button);
    }
    wrapper.append(count, icon, title, translation, choices);
    diagnosticContent.replaceChildren(wrapper);
  }

  async function selectAnswer(questionNode, answer) {
    traversal.push({
      node_id: currentNodeId,
      question: questionNode.question,
      answer_id: answer.id,
      answer: answer.label,
    });
    currentNodeId = answer.next;
    await renderNode();
  }

  function renderResolution(node) {
    const wrapper = document.createElement("div");
    wrapper.className = "outcome-view";
    const icon = document.createElement("div");
    icon.className = "diagnostic-icon outcome-icon";
    icon.textContent = node.icon || "✅";
    const title = document.createElement("h2");
    safeText(title, node.title);
    const translation = document.createElement("p");
    translation.className = "translation";
    safeText(translation, node.translation);
    const steps = document.createElement("ol");
    steps.className = "instruction-list";
    for (const instruction of node.instructions || []) {
      const item = document.createElement("li");
      const stepIcon = document.createElement("span");
      stepIcon.textContent = instruction.icon || "•";
      const text = document.createElement("span");
      safeText(text, instruction.text);
      item.append(stepIcon, text);
      steps.append(item);
    }
    const note = document.createElement("p");
    note.className = "safe-note";
    note.textContent = "Niba ikibazo gikomeje cyangwa wumva utizeye, subira inyuma usabe umutekinisiye.";
    const restart = document.createElement("button");
    restart.type = "button";
    restart.className = "button button-outline button-large";
    restart.textContent = "Ongera utangire / Start over";
    restart.addEventListener("click", startTree);
    wrapper.append(icon, title, translation, steps, note, restart);
    diagnosticContent.replaceChildren(wrapper);
  }

  function createId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.random() * 16 | 0;
      return (character === "x" ? random : (random & 3 | 8)).toString(16);
    });
  }

  async function saveTicket(node) {
    const ticket = {
      client_ticket_id: createId(),
      hardware_id: selectedUnit.hardware_id,
      model_type: selectedUnit.model_type,
      priority: node.priority || "High",
      fault_category: node.fault_category,
      fault_code: {
        code: node.fault_code,
        category: node.fault_category,
        description: node.translation || node.title,
      },
      diagnostic_path: traversal,
      created_at: new Date().toISOString(),
      state: "queued",
    };
    await transact(TICKET_STORE, "readwrite", (store) => store.put(ticket));
    await updateQueueCount();
    const wrapper = document.createElement("div");
    wrapper.className = "outcome-view ticket-outcome";
    const icon = document.createElement("div");
    icon.className = "diagnostic-icon outcome-icon";
    icon.textContent = node.icon || "🧑‍🔧";
    const title = document.createElement("h2");
    safeText(title, node.title || "Twasabye umutekinisiye");
    const translation = document.createElement("p");
    translation.className = "translation";
    safeText(translation, node.translation);
    const code = document.createElement("p");
    code.className = "fault-code";
    code.textContent = `${ticket.fault_code.code} · ${ticket.priority}`;
    const status = document.createElement("p");
    status.className = "safe-note";
    status.textContent = navigator.onLine
      ? "Tike yabitswe. Irahita yoherezwa iyo internet ihari."
      : "Tike yabitswe kuri telefoni. Izoherezwa internet igarutse.";
    const guidance = document.createElement("ul");
    guidance.className = "instruction-list plain-list";
    for (const instruction of node.instructions || []) {
      const item = document.createElement("li");
      safeText(item, instruction);
      guidance.append(item);
    }
    const restart = document.createElement("button");
    restart.type = "button";
    restart.className = "button button-outline button-large";
    restart.textContent = "Tangira irindi genzura";
    restart.addEventListener("click", startTree);
    wrapper.append(icon, title, translation, code, status, guidance, restart);
    diagnosticContent.replaceChildren(wrapper);
    if (navigator.onLine) await syncQueuedTickets();
    else registerBackgroundSync();
  }

  async function renderNode() {
    // The browser only renders the active node; branching stays in the server-provided JSON.
    const node = activeTree?.content?.nodes?.[currentNodeId];
    if (!node) {
      showMessage("Amakuru y’igenzura ntaboneka. Ongera uhuze internet cyangwa uvugane n’umutekinisiye.", "error");
      return;
    }
    if (node.type === "question") renderQuestion(node);
    else if (node.type === "resolution") renderResolution(node);
    else if (node.type === "ticket") await saveTicket(node);
    else showMessage("Iyi nzira y’igenzura irimo ikibazo. Vugana n’umutekinisiye.", "error");
  }

  async function startTree() {
    traversal = [];
    currentNodeId = activeTree.content.start_node;
    await renderNode();
  }

  async function validateUnit(hardwareId, modelType) {
    if (navigator.onLine) {
      const response = await fetch(`${API}/hardware/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ hardware_id: hardwareId, model_type: modelType }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || `Hardware could not be validated (${response.status}).`);
      }
      const unit = await response.json();
      await rememberUnit(unit);
      return unit;
    }
    // Offline validation is limited to units this browser has already verified online.
    const unit = await getCachedUnit(hardwareId, modelType);
    if (!unit) {
      throw new Error("Iyi telefoni ntiyigeze igenzura iyi hardware ID kuri internet. Huza internet uyigenzure rimwe mbere yo gukoresha offline.");
    }
    return unit;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = document.getElementById("start-button");
    const hardwareId = form.elements.hardware_id.value.trim().toUpperCase();
    const modelType = form.elements.model_type.value;
    submit.disabled = true;
    message.hidden = true;
    try {
      if (!database) throw new Error("Offline storage is not ready in this browser.");
      selectedUnit = await validateUnit(hardwareId, modelType);
      activeTree = await getTree(modelType);
      if (!activeTree && navigator.onLine) {
        await refreshTrees();
        activeTree = await getTree(modelType);
      }
      if (!activeTree) throw new Error("Nta giti cy’igenzura kibitswe kuri telefoni. Huza internet ukongera ugerageze.");
      modelLabel.textContent = modelType === "biogas" ? "♨️ Biogaz · " + selectedUnit.hardware_id : "☀️ Imirasire · " + selectedUnit.hardware_id;
      hardwarePanel.hidden = true;
      diagnosticPanel.hidden = false;
      await startTree();
      window.scrollTo({ top: diagnosticPanel.offsetTop - 16, behavior: "smooth" });
    } catch (error) {
      showMessage(error.message || "Habaye ikibazo mu igenzura. Ongera ugerageze.", "error");
    } finally {
      submit.disabled = false;
    }
  });

  document.getElementById("restart-button").addEventListener("click", () => {
    diagnosticPanel.hidden = true;
    hardwarePanel.hidden = false;
  });

  async function syncQueuedTickets() {
    if (!navigator.onLine || !database) return;
    const tickets = (await getAll(TICKET_STORE)).filter((ticket) => ticket.state === "queued");
    if (!tickets.length) return;
    try {
      const response = await fetch(`${API}/tickets/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ tickets: tickets.map(({ state, created_at, ...ticket }) => ticket) }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || `Ticket sync failed (${response.status}).`);
      }
      const result = await response.json();
      // Remove only acknowledged tickets; rejected ones stay visible with their server reason.
      for (const outcome of result.results || []) {
        const ticket = await transact(TICKET_STORE, "readonly", (store) => store.get(outcome.client_ticket_id));
        if (!ticket) continue;
        if (outcome.result === "synced" || outcome.result === "already_synced") {
          await transact(TICKET_STORE, "readwrite", (store) => store.delete(outcome.client_ticket_id));
        } else {
          ticket.state = "rejected";
          ticket.sync_error = outcome.message || "Ticket was rejected by the server.";
          await transact(TICKET_STORE, "readwrite", (store) => store.put(ticket));
        }
      }
      await updateQueueCount();
      if (result.rejected) {
        showMessage(`${result.rejected} tike ntiyoherejwe. Reba nomero ya hardware cyangwa uvugane n’umutekinisiye.`, "error");
      } else {
        showMessage(`${result.synced} tike zoherejwe neza.`, "success");
      }
    } catch (error) {
      showMessage(`Tike iracyabitswe kuri telefoni. Izongera koherezwa internet imaze kugaruka. ${error.message}`, "warning");
    }
  }

  async function registerBackgroundSync() {
    if (!("serviceWorker" in navigator)) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      if ("sync" in registration) await registration.sync.register("ticket-sync");
      else registration.active?.postMessage({ type: "SYNC_TICKETS" });
    } catch (error) {
      console.warn("Background sync is unavailable; tickets will sync when this page is open.", error);
    }
  }

  window.addEventListener("online", () => {
    setConnection();
    void refreshTrees().catch((error) => console.warn("Could not refresh cached decision trees.", error));
    void syncQueuedTickets();
  });
  window.addEventListener("offline", setConnection);

  async function init() {
    setConnection();
    try {
      database = await openDatabase();
      await updateQueueCount();
      if (navigator.onLine) {
        await refreshTrees();
        await syncQueuedTickets();
      }
    } catch (error) {
      showMessage(error.message || "Offline storage could not be initialized.", "error");
    }
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((error) => {
        console.error("Service worker registration failed.", error);
        showMessage("Iyi telefoni ntiyabashije kubika porogaramu offline. Ongera ufungure ukoresheje internet.", "warning");
      });
    }
  }

  void init();
})();
