/* Turns the photographic glass diamond into a living mark.
   A slow 3D rock, a light sweep across the facets, and a soft float.
   The still image stays when motion is reduced, data-saver is on,
   or the phone is low-power. */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var net = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  var cores = navigator.hardwareConcurrency || 8;
  var memory = navigator.deviceMemory || 8;
  var narrow = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  if (reduce || (net && net.saveData) || memory <= 2 || (narrow && cores <= 2)) return;

  var hosts = document.querySelectorAll("[data-narjis-gem]");
  if (!hosts.length) return;

  hosts.forEach(function (host) {
    if (host.querySelector(".gem-sweep")) return;
    var sweep = document.createElement("span");
    sweep.className = "gem-sweep";
    sweep.setAttribute("aria-hidden", "true");
    host.appendChild(sweep);
    host.classList.add("is-live");
  });
})();
