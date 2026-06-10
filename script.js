const form = document.querySelector("#instructionForm");
const input = document.querySelector("#instructionInput");
const statusLine = document.querySelector("#composerStatus");
const attachButton = document.querySelector("#attachButton");
const fileInput = document.querySelector("#fileInput");
const toolsButton = document.querySelector("#toolsButton");
const elementsButton = document.querySelector("#elementsButton");
const toolsMenu = document.querySelector("#toolsMenu");
const elementsMenu = document.querySelector("#elementsMenu");
const selectionNote = document.querySelector("#selectionNote");
const canvasNodes = Array.from(document.querySelectorAll(".canvas-node"));

let activeTool = "Image";

function autoResizeTextarea() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 152)}px`;
}

function closeMenus(except) {
  if (except !== toolsMenu) {
    toolsMenu.hidden = true;
    toolsButton.setAttribute("aria-expanded", "false");
  }

  if (except !== elementsMenu) {
    elementsMenu.hidden = true;
    elementsButton.setAttribute("aria-expanded", "false");
  }
}

function selectNode(nodeName) {
  canvasNodes.forEach((node) => {
    node.classList.toggle("selected", node.dataset.nodeName === nodeName);
  });
  selectionNote.textContent = `${nodeName} selected`;
}

input.addEventListener("input", autoResizeTextarea);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const instruction = input.value.trim();

  if (!instruction) {
    statusLine.textContent = "Write an instruction before sending it to the agent.";
    input.focus();
    return;
  }

  statusLine.textContent = `Instruction sent with ${activeTool}.`;
  input.value = "";
  autoResizeTextarea();
});

attachButton.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  const count = fileInput.files.length;
  if (count > 0) {
    statusLine.textContent = count === 1 ? "1 file attached." : `${count} files attached.`;
  }
});

toolsButton.addEventListener("click", () => {
  const shouldOpen = toolsMenu.hidden;
  closeMenus(toolsMenu);
  toolsMenu.hidden = !shouldOpen;
  toolsButton.setAttribute("aria-expanded", String(shouldOpen));
});

elementsButton.addEventListener("click", () => {
  const shouldOpen = elementsMenu.hidden;
  closeMenus(elementsMenu);
  elementsMenu.hidden = !shouldOpen;
  elementsButton.setAttribute("aria-expanded", String(shouldOpen));
});

toolsMenu.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tool]");
  if (!button) return;

  activeTool = button.dataset.tool;
  toolsButton.textContent = activeTool;
  statusLine.textContent = `Active tool: ${activeTool}.`;
  closeMenus();
  input.focus();
});

elementsMenu.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-target]");
  if (!button) return;

  selectNode(button.dataset.target);
  closeMenus();
  input.focus();
});

canvasNodes.forEach((node) => {
  node.addEventListener("click", () => {
    selectNode(node.dataset.nodeName);
  });
});

document.addEventListener("click", (event) => {
  const clickedInsideComposer = event.target.closest(".composer-wrap");
  if (!clickedInsideComposer) closeMenus();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenus();
});

autoResizeTextarea();
