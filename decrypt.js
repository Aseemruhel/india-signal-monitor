/**
 * India Pulse 360 — Client-side decryption
 * Decrypts data/summary.enc.json in the browser using the Web Crypto API.
 * Must use the exact same PBKDF2 + AES-GCM parameters as encrypt_dashboard.py.
 *
 * Nothing here ever sends the password anywhere — everything happens
 * locally in the browser. If the password is wrong, decryption fails
 * and there is no fallback to plaintext.
 */

const PBKDF2_ITERATIONS_DEFAULT = 250000;

function b64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function deriveKey(passphrase, saltBytes, iterations) {
  const enc = new TextEncoder();
  const passKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(passphrase),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: saltBytes, iterations: iterations, hash: "SHA-256" },
    passKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
}

async function decryptPayload(payload, passphrase) {
  const salt = b64ToBytes(payload.salt);
  const iv = b64ToBytes(payload.iv);
  const ciphertext = b64ToBytes(payload.ciphertext);
  const iterations = payload.iterations || PBKDF2_ITERATIONS_DEFAULT;

  const key = await deriveKey(passphrase, salt, iterations);

  // A wrong password produces a key that fails GCM's built-in integrity
  // check, so subtle.decrypt() throws — there is no partial/garbled
  // plaintext to worry about handling.
  const plaintextBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, key, ciphertext);
  return JSON.parse(new TextDecoder().decode(plaintextBuf));
}

/**
 * Fetches the encrypted JSON at `url`, decrypts it with `passphrase`,
 * and returns the parsed object. Throws on wrong password or bad data.
 */
async function fetchAndDecrypt(url, passphrase) {
  const resp = await fetch(url, { cache: "no-store" });
  if (!resp.ok) throw new Error(`Could not fetch ${url} (${resp.status})`);
  const payload = await resp.json();
  return decryptPayload(payload, passphrase);
}

// ── Lock screen wiring ──────────────────────────────────────────────────
// Expects this HTML structure somewhere on the page (see lock-screen.html):
//   #lock-screen, #dashboard-password, #unlock-btn, #unlock-error, #dashboard-root
//
// On success, calls window.initDashboard(data) if that function exists —
// wire your existing dashboard render logic to that function.

async function unlockDashboard() {
  const passwordInput = document.getElementById("dashboard-password");
  const errorEl = document.getElementById("unlock-error");
  const unlockBtn = document.getElementById("unlock-btn");
  const password = passwordInput.value;

  if (!password) return;

  errorEl.textContent = "";
  unlockBtn.disabled = true;
  unlockBtn.textContent = "Unlocking…";

  try {
    const data = await fetchAndDecrypt("data/summary.enc.json", password);

    document.getElementById("lock-screen").style.display = "none";
    document.getElementById("dashboard-root").style.display = "block";

    // Session-only flag so a refresh within the same tab doesn't need
    // re-fetching immediately re-prompt logic if you add that later.
    // The password itself is never stored anywhere.
    sessionStorage.setItem("ip360_unlocked_at", Date.now().toString());

    if (typeof window.initDashboard === "function") {
      window.initDashboard(data);
    } else {
      console.warn("window.initDashboard(data) not found — wire your dashboard render function to this.");
    }
  } catch (err) {
    errorEl.textContent = "Incorrect password.";
    passwordInput.value = "";
    passwordInput.focus();
  } finally {
    unlockBtn.disabled = false;
    unlockBtn.textContent = "Unlock";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("unlock-btn");
  const input = document.getElementById("dashboard-password");
  if (btn) btn.addEventListener("click", unlockDashboard);
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") unlockDashboard();
    });
    input.focus();
  }
});
