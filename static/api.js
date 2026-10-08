/* =========================================================
   api.js: sab pages ke liye shared helpers
   (tokens, apiFetch, toast, dialog, form errors, highlight)
   ========================================================= */

/* ---------- Tokens ---------- */
function saveTokens(access, refresh) {
  localStorage.setItem("access", access);
  localStorage.setItem("refresh", refresh);
}
function getAccess() { return localStorage.getItem("access"); }
function getRefresh() { return localStorage.getItem("refresh"); }
function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}

/* ---------- API call (token lagata hai, 401 par login par bhejta hai) ---------- */
async function apiFetch(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const token = getAccess();
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 && token) {
    clearTokens();
    flash("Your session ended. Log in again.", "error");
    window.location = "/login/";
  }
  return res;
}

/* Logged-in user (/auth/me/ se), ek baar fetch karke yaad rakho */
let _me = null;
async function getMe() {
  if (_me) return _me;
  const res = await apiFetch("/auth/me/");
  if (res.ok) _me = await res.json();
  return _me;
}

/* ---------- Toast (chhota message neeche) ---------- */
function toast(message, kind) {
  const box = document.getElementById("toasts");
  if (!box) return;
  const el = document.createElement("div");
  el.className = "toast" + (kind === "error" ? " error" : "");
  el.setAttribute("role", kind === "error" ? "alert" : "status");
  el.textContent = message;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* Page badalne ke baad bhi toast dikhane ke liye (sessionStorage mein rakh kar) */
function flash(message, kind) {
  try { sessionStorage.setItem("flash", JSON.stringify({ message, kind })); } catch (e) { /* ignore */ }
}
function showFlash() {
  try {
    const raw = sessionStorage.getItem("flash");
    if (!raw) return;
    sessionStorage.removeItem("flash");
    const f = JSON.parse(raw);
    toast(f.message, f.kind);
  } catch (e) { /* ignore */ }
}

/* ---------- Confirm dialog (window.confirm ki jagah) ---------- */
function confirmDialog(title, text, okLabel) {
  return new Promise((resolve) => {
    const dlg = document.getElementById("confirm-dialog");
    dlg.querySelector("h2").textContent = title;
    dlg.querySelector("p").textContent = text;
    const ok = dlg.querySelector("[data-ok]");
    const cancel = dlg.querySelector("[data-cancel]");
    ok.textContent = okLabel || "Delete";
    const done = (value) => {
      ok.onclick = cancel.onclick = null;
      dlg.onclose = null;
      if (dlg.open) dlg.close();
      resolve(value);
    };
    ok.onclick = () => done(true);
    cancel.onclick = () => done(false);
    dlg.onclose = () => done(false);   // Esc dabane par
    dlg.showModal();
    cancel.focus();
  });
}

/* ---------- Form helpers ---------- */
function setBusy(button, busy, busyText) {
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

/* DRF ka error {field: ["msg"]} har field ke neeche dikhao */
function showErrors(form, data) {
  clearErrors(form);
  let general = [];
  Object.keys(data || {}).forEach((key) => {
    const msgs = Array.isArray(data[key]) ? data[key] : [String(data[key])];
    const input = form.elements[key];
    const slot = form.querySelector('[data-error-for="' + key + '"]');
    if (input && slot) {
      input.setAttribute("aria-invalid", "true");
      slot.textContent = msgs.join(" ");
      slot.hidden = false;
    } else {
      general = general.concat(msgs);
    }
  });
  const box = form.querySelector("[data-form-error]");
  if (box && general.length) {
    box.textContent = general.join(" ");
    box.hidden = false;
  }
  const first = form.querySelector('[aria-invalid="true"]');
  if (first) first.focus();
}

function clearErrors(form) {
  form.querySelectorAll("[aria-invalid]").forEach((i) => i.removeAttribute("aria-invalid"));
  form.querySelectorAll("[data-error-for]").forEach((s) => { s.textContent = ""; s.hidden = true; });
  const box = form.querySelector("[data-form-error]");
  if (box) { box.textContent = ""; box.hidden = true; }
}

/* ---------- Dikhawa ---------- */
function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/* Author ek string ho ya object, dono chalein */
function authorName(a) {
  if (!a) return "";
  if (typeof a === "object") return a.username || "";
  return String(a);
}

/* Naam se gol avatar (rang naam se tay hota hai) */
function makeAvatar(name) {
  const el = document.createElement("span");
  el.className = "avatar";
  el.setAttribute("aria-hidden", "true");
  el.textContent = (name || "?").charAt(0).toUpperCase();
  let h = 0;
  for (const ch of name || "") h = (h * 31 + ch.charCodeAt(0)) % 360;
  el.style.background = "hsl(" + h + " 45% 85%)";
  el.style.color = "hsl(" + h + " 55% 22%)";
  return el;
}

/* Text ke andar search ke lafz <mark> se chamkao (textContent se, XSS se bacha hua) */
function appendHighlighted(parent, text, query) {
  const words = (query || "").split(/\s+/).filter(Boolean)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) { parent.appendChild(document.createTextNode(text)); return; }
  const re = new RegExp("(" + words.join("|") + ")", "gi");
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
    const mark = document.createElement("mark");
    mark.textContent = m[0];
    parent.appendChild(mark);
    last = m.index + m[0].length;
    if (m[0].length === 0) re.lastIndex++;
  }
  if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
}

/* ---------- Navbar ---------- */
function initNav() {
  const loggedIn = !!getAccess();
  document.querySelectorAll("[data-auth='in']").forEach((e) => (e.hidden = !loggedIn));
  document.querySelectorAll("[data-auth='out']").forEach((e) => (e.hidden = loggedIn));

  if (loggedIn) {
    getMe().then((me) => {
      const nameEl = document.getElementById("nav-name");
      const avEl = document.getElementById("nav-avatar");
      if (me && me.username && nameEl && avEl) {
        nameEl.textContent = me.username;
        avEl.replaceWith(Object.assign(makeAvatar(me.username), { id: "nav-avatar" }));
      }
    });
  }

  const logout = document.getElementById("logout-btn");
  if (logout) {
    logout.addEventListener("click", async () => {
      // Server ko bata do ke refresh token ab bekaar hai (agar endpoint chalta hai)
      try {
        await fetch("/auth/logout/", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + getAccess() },
          body: JSON.stringify({ refresh: getRefresh() }),
        });
      } catch (e) { /* network error: phir bhi local logout */ }
      clearTokens();
      flash("Logged out.");
      window.location = "/login/";
    });
  }
  showFlash();
}

document.addEventListener("DOMContentLoaded", initNav);
