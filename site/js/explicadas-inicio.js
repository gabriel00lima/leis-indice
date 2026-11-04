// Seção "Lei explicada" da página inicial.
import { listaExplicadas, cartaoExplicada } from "./explicadas.js";

const grade = document.getElementById("lista-explicadas");
const secao = document.getElementById("explicadas");

listaExplicadas().then(lista => {
  if (!lista.length) { secao.hidden = true; return; }
  grade.replaceChildren(...lista.slice(0, 8).map(cartaoExplicada));
});
