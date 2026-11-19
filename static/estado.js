// Calcula el estado de cada votación en el navegador, para que el sitio
// no dependa de cuándo se generó.
(function () {
  var ETIQUETAS = { proxima: "Próximamente", abierta: "Abierta", cerrada: "Cerrada", borrador: "En preparación" };

  function duracion(ms) {
    var m = Math.max(0, Math.floor(ms / 60000));
    var d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), min = m % 60;
    if (d > 0) return d + (d === 1 ? " día " : " días ") + h + " h";
    if (h > 0) return h + " h " + min + " min";
    return min + " min";
  }

  function actualizar() {
    var ahora = Date.now();
    document.querySelectorAll("[data-apertura], [data-borrador]").forEach(function (el) {
      if (el.dataset.borrador === "1") {
        var prep = el.querySelector("[data-estado]");
        if (prep) {
          prep.className = "estado estado-borrador";
          prep.textContent = ETIQUETAS.borrador;
        }
        el.querySelectorAll("[data-mostrar]").forEach(function (b) {
          b.hidden = b.dataset.mostrar !== "borrador";
        });
        return;
      }
      var ap = Date.parse(el.dataset.apertura), ci = Date.parse(el.dataset.cierre);
      var estado = ahora < ap ? "proxima" : ahora < ci ? "abierta" : "cerrada";
      var badge = el.querySelector("[data-estado]");
      if (badge) {
        badge.className = "estado estado-" + estado;
        badge.textContent = ETIQUETAS[estado];
      }
      el.querySelectorAll("[data-mostrar]").forEach(function (b) {
        b.hidden = b.dataset.mostrar !== estado;
      });
      el.querySelectorAll("[data-cuenta]").forEach(function (c) {
        c.textContent = duracion((c.dataset.cuenta === "apertura" ? ap : ci) - ahora);
      });
    });
  }

  actualizar();
  setInterval(actualizar, 30000);
})();
