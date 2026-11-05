/* Administrator tools for the hardware registry and database-backed JSON trees. */
(() => {
  "use strict";
  const API = "/api/v1";
  const tokenKey = "egisubizo-admin-token";
  const loginPanel = document.getElementById("login-panel");
  const adminPanel = document.getElementById("admin-panel");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const hardwareMessage = document.getElementById("hardware-message");
  const treeMessage = document.getElementById("tree-message");
  const usersMessage = document.getElementById("users-message");
  const treeSelect = document.getElementById("tree-select");
  let token = sessionStorage.getItem(tokenKey);
  let trees = [];

  function showMessage(element, text, kind = "info") {
    element.textContent = text;
    element.className = `notice notice-${kind}`;
    element.hidden = false;
  }

  function setSignedIn(signedIn) {
    loginPanel.hidden = signedIn;
    adminPanel.hidden = !signedIn;
  }

  async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.detail || `Request failed (${response.status}).`);
    }
    return response.json();
  }

  function currentTree() {
    return trees.find((tree) => tree.slug === treeSelect.value);
  }

  function showTree() {
    const tree = currentTree();
    if (!tree) return;
    document.getElementById("tree-version").value = String(tree.version);
    document.getElementById("tree-json").value = JSON.stringify(tree.content, null, 2);
    treeMessage.hidden = true;
  }

  async function loadTrees() {
    trees = await request("/diagnostic-trees");
    treeSelect.replaceChildren();
    for (const tree of trees) {
      const option = document.createElement("option");
      option.value = tree.slug;
      option.textContent = `${tree.content.title || tree.slug} · v${tree.version}`;
      treeSelect.append(option);
    }
    showTree();
  }

  async function loadUsers() {
    const users = await request("/users");
    const rows = document.getElementById("user-rows");
    rows.replaceChildren();
    for (const user of users) {
      const row = document.createElement("tr");
      for (const value of [
        user.username,
        user.role,
        user.district || "—",
        user.sector || "—",
        user.active ? "Active" : "Revoked",
      ]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      const action = document.createElement("td");
      // Keep the current administrator from locking themselves out of the admin UI.
      if (user.id === currentUserId) {
        action.textContent = "Current account";
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button button-small button-outline";
        button.textContent = user.active ? "Revoke" : "Restore";
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await request(`/users/${user.id}/access`, {
              method: "PATCH",
              body: JSON.stringify({ active: !user.active }),
            });
            await loadUsers();
            showMessage(usersMessage, `Access for ${user.username} ${user.active ? "revoked" : "restored"}.`, "success");
          } catch (error) {
            showMessage(usersMessage, error.message, "error");
          } finally {
            button.disabled = false;
          }
        });
        action.append(button);
      }
      row.append(action);
      rows.append(row);
    }
  }

  let currentUserId;

  async function authenticate() {
    const user = await request("/auth/me");
    if (user.role !== "admin") throw new Error("This token does not have administrator access.");
    currentUserId = user.id;
    document.getElementById("admin-identity").textContent = `Signed in: ${user.username}`;
    // Load both admin datasets before revealing any edit controls.
    await Promise.all([loadTrees(), loadUsers()]);
    setSignedIn(true);
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    token = document.getElementById("access-token").value.trim();
    loginError.hidden = true;
    try {
      await authenticate();
      sessionStorage.setItem(tokenKey, token);
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

  document.getElementById("hardware-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    hardwareMessage.hidden = true;
    try {
      const unit = await request("/hardware", {
        method: "POST",
        body: JSON.stringify({
          hardware_id: document.getElementById("hardware-id").value.trim(),
          model_type: document.getElementById("model-type").value,
          district: document.getElementById("district").value.trim(),
          sector: document.getElementById("sector").value.trim(),
        }),
      });
      form.reset();
      showMessage(hardwareMessage, `${unit.hardware_id} registered for ${unit.sector}, ${unit.district}.`, "success");
    } catch (error) {
      showMessage(hardwareMessage, error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  treeSelect.addEventListener("change", showTree);
  document.getElementById("user-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    usersMessage.hidden = true;
    document.getElementById("user-token").hidden = true;
    try {
      const created = await request("/users", {
        method: "POST",
        body: JSON.stringify({
          username: document.getElementById("username").value.trim(),
          role: document.getElementById("user-role").value,
          district: document.getElementById("user-district").value.trim() || null,
          sector: document.getElementById("user-sector").value.trim() || null,
        }),
      });
      form.reset();
      const oneTimeToken = document.getElementById("user-token");
      // The API returns a new credential once; show it now and never store it in the page.
      oneTimeToken.textContent = `Copy this token now for ${created.username}. It will not be shown again: ${created.access_token}`;
      oneTimeToken.hidden = false;
      await loadUsers();
      showMessage(usersMessage, `Created ${created.role} account ${created.username}.`, "success");
    } catch (error) {
      showMessage(usersMessage, error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  document.getElementById("tree-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const tree = currentTree();
    if (!tree) return;
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    treeMessage.hidden = true;
    try {
      let content;
      try {
        content = JSON.parse(document.getElementById("tree-json").value);
      } catch {
        throw new Error("The decision tree is not valid JSON. Correct it before saving.");
      }
      const updated = await request(`/diagnostic-trees/${encodeURIComponent(tree.slug)}`, {
        method: "PUT",
        body: JSON.stringify({
          appliance_type: tree.appliance_type,
          version: tree.version + 1,
          content,
          active: true,
        }),
      });
      trees = trees.map((existing) => existing.slug === updated.slug ? updated : existing);
      const option = treeSelect.selectedOptions[0];
      option.textContent = `${updated.content.title || updated.slug} · v${updated.version}`;
      showTree();
      showMessage(treeMessage, `Saved ${updated.slug} as version ${updated.version}.`, "success");
    } catch (error) {
      showMessage(treeMessage, error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  if (token) {
    void authenticate().then(() => {
      sessionStorage.setItem(tokenKey, token);
    }).catch(() => {
      token = null;
      sessionStorage.removeItem(tokenKey);
      setSignedIn(false);
    });
  }
})();
