/* Authenticated technician dispatch table. The bearer token is held only in sessionStorage. */
(() => {
  "use strict";
  const API = "/api/v1";
  const loginPanel = document.getElementById("login-panel");
  const dispatchPanel = document.getElementById("dispatch-panel");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const dispatchMessage = document.getElementById("dispatch-message");
  const ticketRows = document.getElementById("ticket-rows");
  const emptyState = document.getElementById("empty-state");
  const tokenKey = "egisubizo-technician-token";
  const notificationButton = document.getElementById("notification-button");
  const notificationStatus = document.getElementById("notification-status");
  let token = sessionStorage.getItem(tokenKey);
  let audioContext;
  let pollingTimer;
  let knownTicketIds = new Set();
  let monitoringInitialized = false;
  let notificationsEnabled = false;

  function playAlertSound() {
    if (!notificationsEnabled) return;
    try {
      audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(880, audioContext.currentTime);
      oscillator.frequency.setValueAtTime(660, audioContext.currentTime + 0.12);
      gain.gain.setValueAtTime(0.0001, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.18, audioContext.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.28);
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (error) {
      console.warn("Could not play the ticket alert sound.", error);
    }
  }

  function showBrowserNotification(ticket) {
    if (!notificationsEnabled || !("Notification" in window) || Notification.permission !== "granted") return;
    const hardware = ticket.hardware_id || "Unknown hardware";
    new Notification("New E-Gisubizo service ticket", {
      body: `${hardware} · ${ticket.priority} · ${ticket.fault_category}`,
      tag: `egisubizo-ticket-${ticket.id}`,
      icon: "/icon.svg",
    });
  }

  async function enableNotifications() {
    notificationsEnabled = true;
    try {
      if ("Notification" in window && Notification.permission === "default") {
        await Notification.requestPermission();
      }
      if (audioContext && audioContext.state === "suspended") await audioContext.resume();
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        await audioContext.resume();
      }
      playAlertSound();
    } catch (error) {
      console.warn("Notification setup failed.", error);
    }
    updateNotificationStatus();
  }

  function updateNotificationStatus() {
    if (!notificationsEnabled) {
      notificationStatus.textContent = "Sound and browser alerts are off.";
      notificationButton.textContent = "Enable sound & alerts";
      return;
    }
    const browserPermission = ("Notification" in window)
      ? Notification.permission
      : "unsupported";
    notificationStatus.textContent = browserPermission === "granted"
      ? "Sound and browser alerts are enabled."
      : "Sound is enabled; browser notification permission was not granted.";
    notificationButton.textContent = "Alerts enabled";
  }

  async function checkForNewTickets() {
    if (!token) return;
    try {
      const tickets = await api("/tickets");
      const currentIds = new Set(tickets.map((ticket) => ticket.id));
      if (!monitoringInitialized) {
        knownTicketIds = currentIds;
        monitoringInitialized = true;
        return;
      }
      const newTickets = tickets.filter((ticket) =>
        !knownTicketIds.has(ticket.id) && ["Open", "InProgress"].includes(ticket.status)
      );
      knownTicketIds = currentIds;
      if (newTickets.length) {
        playAlertSound();
        showBrowserNotification(newTickets[0]);
        showNotice(
          `${newTickets.length} new service ${newTickets.length === 1 ? "ticket" : "tickets"} received.`,
          "success",
        );
        await loadTickets();
      }
    } catch (error) {
      console.warn("Could not check for new tickets.", error);
    }
  }

  function startTicketPolling() {
    window.clearInterval(pollingTimer);
    pollingTimer = window.setInterval(checkForNewTickets, 15000);
  }

  function stopTicketPolling() {
    window.clearInterval(pollingTimer);
    pollingTimer = undefined;
  }

  function showNotice(text, kind = "info") {
    dispatchMessage.textContent = text;
    dispatchMessage.className = `notice notice-${kind}`;
    dispatchMessage.hidden = false;
  }

  function setSignedIn(signedIn) {
    loginPanel.hidden = signedIn;
    dispatchPanel.hidden = !signedIn;
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
    // A revoked or expired credential returns the view to the sign-in form.
    if (response.status === 401) {
      token = null;
      sessionStorage.removeItem(tokenKey);
      stopTicketPolling();
      monitoringInitialized = false;
      knownTicketIds = new Set();
      setSignedIn(false);
    }
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.detail || `Request failed (${response.status}).`);
    }
    return response.json();
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function renderRows(tickets) {
    ticketRows.replaceChildren();
    for (const ticket of tickets) {
      const row = document.createElement("tr");
      const status = element("td");
      status.append(element("span", ticket.status, `status-pill status-${ticket.status.toLowerCase()}`));
      const priority = element("td");
      priority.append(element("span", ticket.priority, `priority-pill priority-${ticket.priority.toLowerCase()}`));
      const hardware = element("td");
      hardware.append(element("strong", ticket.hardware_id, "hardware-cell"));
      hardware.append(element("small", ticket.fault_code?.code || ""));
      row.append(
        status,
        priority,
        hardware,
        element("td", ticket.customer_phone || "Not provided"),
        element("td", ticket.fault_category),
        element("td", `${ticket.sector} / ${ticket.district}`),
        element("td", new Date(ticket.created_at).toLocaleString()),
      );
      const actionCell = element("td");
      const form = document.createElement("form");
      form.className = "status-update-form";
      const select = document.createElement("select");
      select.setAttribute("aria-label", `Update status for ticket ${ticket.id}`);
      for (const value of ["Open", "InProgress", "Resolved", "Closed"]) {
        const option = element("option", value);
        option.value = value;
        option.selected = value === ticket.status;
        select.append(option);
      }
      const button = element("button", "Save", "button button-small button-primary");
      button.type = "submit";
      form.append(select, button);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        button.disabled = true;
        try {
          await api(`/tickets/${ticket.id}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status: select.value }),
          });
          showNotice(`Ticket ${ticket.id} updated to ${select.value}.`, "success");
          await loadTickets();
        } catch (error) {
          showNotice(error.message, "error");
        } finally {
          button.disabled = false;
        }
      });
      actionCell.append(form);
      row.append(actionCell);
      ticketRows.append(row);
    }
    document.getElementById("dispatch-count").textContent = `${tickets.length} ${tickets.length === 1 ? "ticket" : "tickets"}`;
    emptyState.hidden = tickets.length !== 0;
  }

  async function loadTickets() {
    const query = new URLSearchParams();
    const status = document.getElementById("status-filter").value;
    const priority = document.getElementById("priority-filter").value;
    if (status) query.set("status", status);
    if (priority) query.set("priority", priority);
    try {
      renderRows(await api(`/tickets?${query.toString()}`));
      dispatchMessage.hidden = true;
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.hidden = true;
    const username = document.getElementById("username-login").value.trim();
    const password = document.getElementById("password-login").value;
    try {
      const loginResponse = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const login = await loginResponse.json().catch(() => ({}));
      if (!loginResponse.ok) throw new Error(login.detail || "Sign-in failed.");
      if (!["technician", "admin"].includes(login.user.role)) throw new Error("This account does not have dispatch access.");
      token = login.access_token;
      const tickets = await api(`/tickets`);
      sessionStorage.setItem(tokenKey, token);
      setSignedIn(true);
      renderRows(tickets);
      knownTicketIds = new Set(tickets.map((ticket) => ticket.id));
      monitoringInitialized = true;
      startTicketPolling();
    } catch (error) {
      token = null;
      document.getElementById("password-login").value = "";
      loginError.textContent = error.message || "Could not sign in. Check your username and password.";
      loginError.hidden = false;
    }
  });

  document.getElementById("signout-button").addEventListener("click", async () => {
    if (token) {
      try {
        await fetch(`${API}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (error) {
        console.warn("Could not revoke the password-login session.", error);
      }
    }
    token = null;
    sessionStorage.removeItem(tokenKey);
    stopTicketPolling();
    monitoringInitialized = false;
    knownTicketIds = new Set();
    setSignedIn(false);
  });
  document.getElementById("refresh-button").addEventListener("click", loadTickets);
  document.getElementById("status-filter").addEventListener("change", loadTickets);
  document.getElementById("priority-filter").addEventListener("change", loadTickets);
  notificationButton.addEventListener("click", enableNotifications);

  if (token) {
    setSignedIn(true);
    void (async () => {
      await loadTickets();
      try {
        const tickets = await api("/tickets");
        knownTicketIds = new Set(tickets.map((ticket) => ticket.id));
        monitoringInitialized = true;
        startTicketPolling();
      } catch (error) {
        console.warn("Could not initialize ticket polling.", error);
      }
    })();
  }
})();
