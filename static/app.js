// ==========================================================
// Sistema de Asistencia - un poco de JavaScript
// Todo esto es solo para comodidad: las validaciones de verdad
// se hacen en el servidor (logica.py).
// ==========================================================

// 1) Reloj en vivo en la pantalla principal
const reloj = document.getElementById("reloj");
if (reloj) {
  function actualizarReloj() {
    const ahora = new Date();
    const horas = String(ahora.getHours()).padStart(2, "0");
    const minutos = String(ahora.getMinutes()).padStart(2, "0");
    reloj.textContent = horas + ":" + minutos;
  }
  actualizarReloj();
  setInterval(actualizarReloj, 5000);
}

// 2) Los campos de DNI solo aceptan números
document.querySelectorAll(".solo-numeros").forEach(function (campo) {
  campo.addEventListener("input", function () {
    campo.value = campo.value.replace(/[^0-9]/g, "");
  });
});

// 3) Cerrar mensajes con la "×" y ocultar solos los de éxito
document.querySelectorAll(".mensaje").forEach(function (mensaje) {
  function cerrar() {
    mensaje.classList.add("saliendo");
    setTimeout(function () { mensaje.remove(); }, 300);
  }
  mensaje.querySelector(".cerrar-mensaje").addEventListener("click", cerrar);
  if (mensaje.classList.contains("mensaje-exito")) {
    setTimeout(cerrar, 6000);
  }
});

// 4) Botones que piden confirmación con un segundo clic (sin ventanas de alert)
document.querySelectorAll("[data-confirmar]").forEach(function (boton) {
  const textoOriginal = boton.textContent;
  boton.addEventListener("click", function (evento) {
    if (boton.dataset.listo === "si") return;   // segundo clic: se envía el formulario
    evento.preventDefault();
    boton.dataset.listo = "si";
    boton.textContent = boton.dataset.confirmar;
    boton.classList.add("confirmando");
    setTimeout(function () {                    // si no confirma en 4 segundos, vuelve atrás
      boton.dataset.listo = "";
      boton.textContent = textoOriginal;
      boton.classList.remove("confirmando");
    }, 4000);
  });
});

// 5) Carga manual: la hora de llegada solo se pide para TARDANZA
const selectorEstado = document.getElementById("manual-estado");
if (selectorEstado) {
  const grupoHora = document.getElementById("grupo-hora");
  const campoHora = document.getElementById("manual-hora");
  function actualizarHora() {
    const esTardanza = selectorEstado.value === "TARDANZA";
    grupoHora.classList.toggle("oculto", !esTardanza);
    campoHora.required = esTardanza;
  }
  selectorEstado.addEventListener("change", actualizarHora);
  actualizarHora();
}

// 6) Buscador de la tabla de alumnos
const filtro = document.getElementById("filtro-alumnos");
if (filtro) {
  const filas = document.querySelectorAll("#tabla-alumnos tbody tr");
  const sinResultados = document.getElementById("sin-resultados");
  filtro.addEventListener("input", function () {
    const texto = filtro.value.trim().toLowerCase();
    let visibles = 0;
    filas.forEach(function (fila) {
      const coincide = fila.textContent.toLowerCase().includes(texto);
      fila.classList.toggle("oculto", !coincide);
      if (coincide) visibles++;
    });
    sinResultados.classList.toggle("oculto", visibles > 0);
  });
}

// 7) Registro de docente: marca en verde las reglas de la contraseña que se cumplen
const campoClave = document.getElementById("clave");
const reglasClave = document.getElementById("reglas-clave");
if (campoClave && reglasClave) {
  const pruebas = {
    largo: function (c) { return c.length >= 8; },
    letra: function (c) { return /\p{L}/u.test(c); },
    numero: function (c) { return /[0-9]/.test(c); },
    especial: function (c) { return /[^\p{L}\p{N}\s]/u.test(c); },
  };
  campoClave.addEventListener("input", function () {
    reglasClave.querySelectorAll("li").forEach(function (regla) {
      regla.classList.toggle("cumple", pruebas[regla.dataset.regla](campoClave.value));
    });
  });
}

// 8) Ojito: muestra u oculta lo que se escribe en los campos de contraseña
document.querySelectorAll(".ver-clave").forEach(function (boton) {
  const campo = boton.parentElement.querySelector("input");
  boton.addEventListener("click", function () {
    const mostrar = campo.type === "password";
    campo.type = mostrar ? "text" : "password";
    const texto = mostrar ? "Ocultar contraseña" : "Mostrar contraseña";
    boton.setAttribute("aria-pressed", mostrar ? "true" : "false");
    boton.setAttribute("aria-label", texto);
    boton.title = texto;
    campo.focus();
  });
});

// Por seguridad, al enviar el formulario las contraseñas vuelven a ocultarse
document.querySelectorAll("form").forEach(function (formulario) {
  formulario.addEventListener("submit", function () {
    formulario.querySelectorAll(".ver-clave[aria-pressed='true']").forEach(function (boton) {
      boton.click();
    });
  });
});

// 9) Dashboard: al pasar el mouse (o el foco del teclado) por una columna del
//    gráfico, se muestra un globo con el detalle de ese día.
const grafico = document.getElementById("grafico-dias");
if (grafico) {
  const globo = document.createElement("div");
  globo.className = "globo oculto";
  globo.setAttribute("role", "status");
  grafico.appendChild(globo);

  function fila(clase, texto, valor) {
    return '<div class="globo-fila"><span class="muestra ' + clase + '"></span>' +
           "<span>" + texto + "</span><span>" + valor + "</span></div>";
  }

  function mostrar(columna) {
    const d = columna.dataset;
    globo.innerHTML = "<strong>" + d.fecha + "</strong>" +
      fila("muestra-presente", "Presentes", d.presentes) +
      fila("muestra-tardanza", "Tardanzas", d.tardanzas) +
      fila("muestra-ausente", "Ausentes", d.ausentes);
    const caja = grafico.getBoundingClientRect();
    const pila = columna.querySelector(".columna-pila").getBoundingClientRect();
    let x = pila.left + pila.width / 2 - caja.left;
    const mitad = 95;                                   // que el globo no se salga por los costados
    x = Math.max(mitad, Math.min(caja.width - mitad, x));
    globo.style.left = x + "px";
    globo.style.top = (pila.top - caja.top - 30) + "px";
    globo.classList.remove("oculto");
  }

  function ocultar() { globo.classList.add("oculto"); }

  grafico.querySelectorAll(".columna").forEach(function (columna) {
    columna.addEventListener("mouseenter", function () { mostrar(columna); });
    columna.addEventListener("focus", function () { mostrar(columna); });
    columna.addEventListener("mouseleave", ocultar);
    columna.addEventListener("blur", ocultar);
  });
}
