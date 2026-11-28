(() => {
  "use strict";
  const panel = document.getElementById("njInlineDetail");
  if (!panel || typeof panel.showModal !== "function") return;
  const title = document.getElementById("njInlineDetailTitle");
  const desc = document.getElementById("njInlineDetailDescription");
  const page = document.getElementById("njInlineDetailLink");
  let origin = null;
  let backToCeo = false;

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const link = event.target.closest("a[data-workshop-detail]");
    if (!link || panel.open) return;
    event.preventDefault();
    origin = link;
    backToCeo = false;
    title.textContent = link.dataset.title || link.textContent.trim();
    desc.textContent = link.dataset.description || "";
    page.href = link.href;
    panel.showModal();
  });
  panel.querySelector("[data-detail-ceo]").addEventListener("click", () => {
    backToCeo = true;
    panel.close();
  });
  panel.addEventListener("close", () => {
    if (backToCeo) document.getElementById("heroCeo")?.click();
    else origin?.focus({ preventScroll: true });
    origin = null;
    backToCeo = false;
  });
})();
