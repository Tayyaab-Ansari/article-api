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