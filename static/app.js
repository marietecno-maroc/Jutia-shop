// app.js
async function api(url, data) {
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  });
  return r.json();
}

async function updateCartBadge() {
  try {
    const r = await fetch("/api/cart/count");
    const d = await r.json();
    const b = document.getElementById("cartBadge");
    if (b) b.textContent = d.count;
  } catch (e) {}
}

async function addToCart(id, qty = 1) {
  const r = await api("/api/cart/add", {id, qty});
  if (r.ok) {
    await updateCartBadge();
    showToast("✅ أُضيف إلى السلة");
  }
}

async function updateQty(id, qty) {
  await api("/api/cart/update", {id, qty});
  location.reload();
}

function showToast(msg) {
  const t = document.createElement("div");
  t.textContent = msg;
  t.style.cssText = `
    position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
    background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;
    padding:14px 24px;border-radius:14px;font-weight:700;z-index:999;
    box-shadow:0 10px 40px rgba(124,58,237,.5);animation:pop .3s ease-out;
  `;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

document.addEventListener("DOMContentLoaded", updateCartBadge);
