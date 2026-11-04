// Menu recolhível do topo no celular (botão "Menu" em .topo-com-menu).
(function () {
  const topo = document.querySelector(".topo-com-menu");
  const botao = topo && topo.querySelector(".menu-botao");
  if (!botao) return;
  const fechar = () => { topo.classList.remove("menu-aberto"); botao.setAttribute("aria-expanded", "false"); };
  botao.addEventListener("click", () => {
    const aberto = topo.classList.toggle("menu-aberto");
    botao.setAttribute("aria-expanded", String(aberto));
  });
  topo.querySelectorAll(".menu a").forEach(a => a.addEventListener("click", fechar));
  document.addEventListener("keydown", ev => { if (ev.key === "Escape") fechar(); });
  document.addEventListener("click", ev => { if (!topo.contains(ev.target)) fechar(); });
})();
