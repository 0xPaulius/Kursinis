// Prisijungimo puslapio logika (perkelta iš login.html, kad neliktų inline skriptų).
(function () {
  // If already logged in, redirect to dashboard
  if (sessionStorage.getItem("auth_token")) {
    window.location.replace("/");
    return;
  }

  const form     = document.getElementById("login-form");
  const userEl   = document.getElementById("username");
  const passEl   = document.getElementById("password");
  const btnEl    = document.getElementById("submit-btn");
  const errBanner= document.getElementById("error-banner");
  const errText  = document.getElementById("error-text");
  const userErr  = document.getElementById("username-err");
  const passErr  = document.getElementById("password-err");
  const togglePw = document.getElementById("toggle-pw");

  togglePw.addEventListener("click", () => {
    const show = passEl.type === "password";
    passEl.type     = show ? "text" : "password";
    togglePw.textContent = show ? "Slėpti" : "Rodyti";
  });

  function clearErrors() {
    errBanner.classList.add("hidden");
    userErr.classList.add("hidden");
    passErr.classList.add("hidden");
    userEl.classList.remove("border-red-400");
    passEl.classList.remove("border-red-400");
  }

  function showFieldError(fieldEl, errEl, msg) {
    fieldEl.classList.add("border-red-400");
    errEl.textContent = msg;
    errEl.classList.remove("hidden");
  }

  function showBannerError(msg) {
    errText.textContent = msg;
    errBanner.classList.remove("hidden");
  }

  function validate() {
    let ok = true;
    clearErrors();
    if (!userEl.value.trim()) {
      showFieldError(userEl, userErr, "Vartotojo vardas negali būti tuščias");
      ok = false;
    }
    if (!passEl.value) {
      showFieldError(passEl, passErr, "Slaptažodis negali būti tuščias");
      ok = false;
    }
    return ok;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validate()) return;

    btnEl.disabled = true;
    btnEl.textContent = "Jungiamasi...";

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: userEl.value.trim(),
          password: passEl.value,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        sessionStorage.setItem("auth_token",  data.token);
        sessionStorage.setItem("auth_user",   data.username);
        window.location.replace("/");
      } else {
        const err = await res.json().catch(() => ({}));
        if (res.status === 401) {
          showBannerError(err.detail || "Neteisingas vartotojo vardas arba slaptažodis");
          passEl.value = "";
          passEl.focus();
        } else if (res.status === 400) {
          showBannerError(err.detail || "Užpildykite visus laukus");
        } else {
          showBannerError("Serverio klaida. Bandykite vėliau.");
        }
      }
    } catch {
      showBannerError("Nepavyko prisijungti prie serverio. Patikrinkite ryšį.");
    } finally {
      btnEl.disabled = false;
      btnEl.textContent = "Prisijungti";
    }
  });
}());
