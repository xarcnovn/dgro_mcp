// dgro UI helpers: live refresh while background steps run, double-submit protection, confirmations.
(function () {
  "use strict";

  // Forms the user has edited but not submitted: never reload over their work.
  let dirty = false;
  document.addEventListener("input", (e) => {
    if (e.target.closest("form[data-track]")) dirty = true;
  });

  document.addEventListener("submit", (e) => {
    const form = e.target;
    const submitter = e.submitter;
    const question = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
    if (question && !window.confirm(question)) {
      e.preventDefault();
      return;
    }
    dirty = false;
    // Disable the clicked button after the browser has captured its name/value.
    if (submitter) setTimeout(() => submitter.classList.add("is-busy"), 0);
  });

  // "Select all" checkboxes
  document.querySelectorAll("[data-select-all]").forEach((box) => {
    box.addEventListener("change", () => {
      document.querySelectorAll(`input[name="${box.dataset.selectAll}"]`).forEach((cb) => {
        if (!cb.disabled) cb.checked = box.checked;
      });
    });
  });

  // Case page: poll the status endpoint and refresh when something changed.
  const root = document.querySelector("[data-case-id]");
  if (!root) return;
  const caseId = root.dataset.caseId;
  let version = root.dataset.version;
  let busy = root.dataset.busy === "1";
  const banner = document.getElementById("updates-banner");

  async function poll() {
    try {
      const res = await fetch(`/cases/${caseId}/status`, { headers: { Accept: "application/json" } });
      if (res.ok) {
        const data = await res.json();
        const label = document.getElementById("busy-label");
        if (label && data.jobs.length) label.textContent = data.jobs.join(" · ") + "…";
        if (data.version !== version || data.busy !== busy) {
          if (dirty) {
            if (banner) banner.hidden = false;
          } else {
            const url = new URL(window.location.href);
            url.searchParams.delete("notice");
            url.searchParams.delete("error");
            window.location.replace(url.toString());
            return;
          }
          version = data.version;
          busy = data.busy;
        }
      }
    } catch (err) {
      /* server restarting - try again later */
    }
    setTimeout(poll, busy ? 2000 : 10000);
  }
  setTimeout(poll, busy ? 1500 : 10000);
})();
