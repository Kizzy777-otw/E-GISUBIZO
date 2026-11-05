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
  let token = sessionStorage.getItem(tokenKey);

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
    token = document.getElementById("access-token").value.trim();
    loginError.hidden = true;
    try {
      const response = await fetch(`${API}/tickets`, {
        headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || "Sign-in failed.");
      }
      sessionStorage.setItem(tokenKey, token);
      setSignedIn(true);
      renderRows(await response.json());
    } catch (error) {
      token = null;
      document.getElementById("access-token").value = "";
      loginError.textContent = error.message || "Could not sign in. Check your connection and token.";
      loginError.hidden = false;
    }
  });

  document.getElementById("signout-button").addEventListener("click", () => {
    token = null;
    sessionStorage.removeItem(tokenKey);
    setSignedIn(false);
  });
  document.getElementById("refresh-button").addEventListener("click", loadTickets);
  document.getElementById("status-filter").addEventListener("change", loadTickets);
  document.getElementById("priority-filter").addEventListener("change", loadTickets);

  if (token) {
    setSignedIn(true);
    void loadTickets();
  }
})();
