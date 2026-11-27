// ==========================================================
// Sistema de Asistencia - JavaScript de la interfaz
// Todo esto es solo para comodidad: las validaciones de verdad
// se hacen en el servidor (asistencia/validaciones.py y servicios/).
// ==========================================================

const raiz = document.documentElement;

// 0) Modo claro / oscuro. El tema inicial lo aplica un script en el <head>
//    (para que no parpadee); acá se cambia y se guarda la preferencia.
const botonTema = document.getElementById("boton-tema");
if (botonTema) {
  function actualizarBotonTema() {
    const oscuro = raiz.dataset.tema === "oscuro";
    const texto = oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
    botonTema.setAttribute("aria-label", texto);
    botonTema.title = texto;
    botonTema.setAttribute("aria-pressed", oscuro ? "true" : "false");
  }
  botonTema.addEventListener("click", function () {
    raiz.dataset.tema = raiz.dataset.tema === "oscuro" ? "claro" : "oscuro";
    localStorage.setItem("tema", raiz.dataset.tema);
    actualizarBotonTema();
  });
  actualizarBotonTema();
}

// 1) Menú lateral. En computadora se abre/cierra y se recuerda; en
//    celular (pantallas angostas) arranca oculto y se abre encima.
const botonMenu = document.getElementById("boton-menu");
if (botonMenu) {
  const pantallaAngosta = window.matchMedia("(max-width: 960px)");
  const fondoMenu = document.getElementById("fondo-menu");

  function menuVisible() {
    return pantallaAngosta.matches
      ? raiz.classList.contains("menu-abierto")
      : raiz.dataset.sidebar !== "cerrado";
  }
  function actualizarBotonMenu() {
    botonMenu.setAttribute("aria-expanded", menuVisible() ? "true" : "false");
  }
  function cerrarMenuCelular() {
    raiz.classList.remove("menu-abierto");
    actualizarBotonMenu();
  }

  botonMenu.addEventListener("click", function () {
    if (pantallaAngosta.matches) {
      raiz.classList.toggle("menu-abierto");
    } else {
      const cerrado = raiz.dataset.sidebar === "cerrado";
      if (cerrado) {
        delete raiz.dataset.sidebar;
        localStorage.removeItem("sidebar");
      } else {
        raiz.dataset.sidebar = "cerrado";
        localStorage.setItem("sidebar", "cerrado");
      }
    }
    actualizarBotonMenu();
  });
  fondoMenu.addEventListener("click", cerrarMenuCelular);
  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape") cerrarMenuCelular();
  });
  pantallaAngosta.addEventListener("change", cerrarMenuCelular);
  actualizarBotonMenu();
}

// 2) Reloj en vivo en la pantalla de registro
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

// 3) Los campos de DNI solo aceptan números
document.querySelectorAll(".solo-numeros").forEach(function (campo) {
  campo.addEventListener("input", function () {
    campo.value = campo.value.replace(/[^0-9]/g, "");
  });
});

// 4) Cerrar mensajes con la "×" y ocultar solos los de éxito
document.querySelectorAll(".mensaje").forEach(function (mensaje) {
  const boton = mensaje.querySelector(".cerrar-mensaje");
  if (!boton) return;
  function cerrar() {
    mensaje.classList.add("saliendo");
    setTimeout(function () { mensaje.remove(); }, 300);
  }
  boton.addEventListener("click", cerrar);
  if (mensaje.classList.contains("mensaje-exito")) {
    setTimeout(cerrar, 6000);
  }
});

// 5) Botones que piden confirmación con un segundo clic (sin ventanas de alert)
document.querySelectorAll("[data-confirmar]").forEach(function (boton) {
  // Se guarda el contenido original (puede ser un ícono) para restaurarlo.
  const contenidoOriginal = Array.from(boton.childNodes);
  boton.addEventListener("click", function (evento) {
    if (boton.dataset.listo === "si") return;   // segundo clic: se envía el formulario
    evento.preventDefault();
    boton.dataset.listo = "si";
    boton.textContent = boton.dataset.confirmar;
    boton.classList.add("confirmando");
    setTimeout(function () {                    // si no confirma en 4 segundos, vuelve atrás
      boton.dataset.listo = "";
      boton.replaceChildren(...contenidoOriginal);
      boton.classList.remove("confirmando");
    }, 4000);
  });
});

// 6) Carga manual: la hora de llegada solo se pide para TARDANZA
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

// 7) Buscador de la tabla de alumnos
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

// 8) Registro de cuenta: marca las reglas de la contraseña que se cumplen
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

// 9) Ojito: muestra u oculta lo que se escribe en los campos de contraseña
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

// 10) Globos (tooltips) de los gráficos.
//     Cada marca con data-titulo y data-filas ("Etiqueta|valor;Etiqueta|valor")
//     muestra un globo al pasar el mouse o al llegar con el teclado.
//     Se arma con textContent: los nombres nunca se interpretan como HTML.
function crearGlobo(contenedor) {
  const globo = document.createElement("div");
  globo.className = "globo oculto";
  globo.setAttribute("role", "status");
  contenedor.appendChild(globo);
  return globo;
}

function llenarGlobo(globo, titulo, filas) {
  globo.replaceChildren();
  const fuerte = document.createElement("strong");
  fuerte.textContent = titulo;
  globo.appendChild(fuerte);
  filas.forEach(function (fila) {
    const div = document.createElement("div");
    div.className = "globo-fila";
    if (fila.muestra) {
      const muestra = document.createElement("span");
      muestra.className = "muestra " + fila.muestra;
      div.appendChild(muestra);
    }
    const etiqueta = document.createElement("span");
    etiqueta.textContent = fila.etiqueta;
    const valor = document.createElement("span");
    valor.textContent = fila.valor;
    div.append(etiqueta, valor);
    globo.appendChild(div);
  });
}

function ubicarGlobo(globo, contenedor, objetivo) {
  const caja = contenedor.getBoundingClientRect();
  const marca = objetivo.getBoundingClientRect();
  const mitad = 95;   // que el globo no se salga por los costados
  let x = marca.left + marca.width / 2 - caja.left;
  x = Math.max(mitad, Math.min(caja.width - mitad, x));
  globo.style.left = x + "px";
  globo.style.top = (marca.top - caja.top - 8) + "px";
  globo.classList.remove("oculto");
}

function leerFilas(texto) {
  return (texto || "").split(";").filter(Boolean).map(function (parte) {
    const [etiqueta, valor, muestra] = parte.split("|");
    return { etiqueta: etiqueta, valor: valor, muestra: muestra };
  });
}

document.querySelectorAll("[data-globos]").forEach(function (contenedor) {
  const globo = crearGlobo(contenedor);
  const cruz = contenedor.querySelector(".svg-cruz");
  contenedor.querySelectorAll("[data-titulo]").forEach(function (marca) {
    function mostrar() {
      llenarGlobo(globo, marca.dataset.titulo, leerFilas(marca.dataset.filas));
      const ancla = marca.dataset.ancla
        ? contenedor.querySelector("#" + marca.dataset.ancla) : marca;
      ubicarGlobo(globo, contenedor, ancla || marca);
      if (cruz && marca.dataset.x) {        // línea vertical del gráfico de línea
        cruz.setAttribute("x1", marca.dataset.x);
        cruz.setAttribute("x2", marca.dataset.x);
        cruz.classList.remove("oculto");
      }
    }
    function ocultar() {
      globo.classList.add("oculto");
      if (cruz) cruz.classList.add("oculto");
    }
    marca.addEventListener("mouseenter", mostrar);
    marca.addEventListener("focus", mostrar);
    marca.addEventListener("mouseleave", ocultar);
    marca.addEventListener("blur", ocultar);
  });
});

// 11) Dashboard: globo con el detalle de cada día del gráfico de columnas.
const grafico = document.getElementById("grafico-dias");
if (grafico) {
  const globo = crearGlobo(grafico);
  grafico.querySelectorAll(".columna").forEach(function (columna) {
    function mostrar() {
      const d = columna.dataset;
      llenarGlobo(globo, d.fecha, [
        { etiqueta: "Presentes", valor: d.presentes, muestra: "muestra-presente" },
        { etiqueta: "Tardanzas", valor: d.tardanzas, muestra: "muestra-tardanza" },
        { etiqueta: "Ausentes", valor: d.ausentes, muestra: "muestra-ausente" },
      ]);
      ubicarGlobo(globo, grafico, columna.querySelector(".columna-pila"));
    }
    function ocultar() { globo.classList.add("oculto"); }
    columna.addEventListener("mouseenter", mostrar);
    columna.addEventListener("focus", mostrar);
    columna.addEventListener("mouseleave", ocultar);
    columna.addEventListener("blur", ocultar);
  });
}
