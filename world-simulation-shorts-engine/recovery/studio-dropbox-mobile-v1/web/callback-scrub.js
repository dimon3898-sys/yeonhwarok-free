/* Remove the one-use OAuth code before loading UI assets; never print it. */
(function () {
  "use strict";
  if (window.top !== window.self) {
    window.__worldConnectBlocked = "EMBEDDED_PAGE_REJECTED";
    return;
  }
  if (location.search || location.hash) {
    window.__worldConnectCallback = location.href;
    history.replaceState(null, "", location.pathname);
  }
})();
