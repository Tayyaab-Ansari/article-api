function saveTokens(access, refresh) {
  localStorage.setItem("access", access);
  localStorage.setItem("refresh", refresh);
}

function getAccess() {
  return localStorage.getItem("access");
}

function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}

// Navbar: logged in ho to Logout dikhao, warna Login
if (getAccess()) {
  document.getElementById("login-link").hidden = true;
  const out = document.getElementById("logout-link");
  out.hidden = false;
  out.addEventListener("click", (e) => {
    e.preventDefault();
    clearTokens();
    window.location = "/login/";
  });
}
// Har protected API call isi se karo: token header khud lag jata hai
async function apiFetch(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    Authorization: "Bearer " + getAccess(),
  };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    // token nahi hai ya expire ho gaya: dobara login
    clearTokens();
    window.location = "/login/";
  }
  return res;
}