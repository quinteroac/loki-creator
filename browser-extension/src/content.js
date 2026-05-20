function visibleText(element) {
  return (element?.innerText || element?.textContent || "").trim();
}

function serializePageState() {
  const controls = Array.from(document.querySelectorAll("input, textarea, select, button"))
    .slice(0, 60)
    .map((element) => ({
      ariaLabel: element.getAttribute("aria-label"),
      id: element.id,
      name: element.getAttribute("name"),
      placeholder: element.getAttribute("placeholder"),
      tag: element.tagName.toLowerCase(),
      text: visibleText(element),
      type: element.getAttribute("type"),
    }));
  const links = Array.from(document.querySelectorAll("a[href]"))
    .slice(0, 40)
    .map((link) => ({
      href: link.href,
      text: visibleText(link),
    }));

  return {
    controls,
    links,
    text: visibleText(document.body).slice(0, 6000),
  };
}

function imageToDataUrl(image) {
  const canvas = document.createElement("canvas");
  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;

  if (!width || !height) {
    return null;
  }

  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d")?.drawImage(image, 0, 0, width, height);

  try {
    return canvas.toDataURL("image/png");
  } catch {
    return null;
  }
}

function serializeImages() {
  return Array.from(document.images)
    .map((image) => {
      const rect = image.getBoundingClientRect();
      const dataUrl = image.complete ? imageToDataUrl(image) : null;

      return {
        alt: image.alt || image.getAttribute("aria-label") || "",
        src: image.currentSrc || image.src || "",
        dataUrl,
        width: image.naturalWidth || Math.round(rect.width),
        height: image.naturalHeight || Math.round(rect.height),
        rect: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
      };
    })
    .filter((image) => image.src || image.dataUrl)
    .sort((a, b) => b.rect.width * b.rect.height - a.rect.width * a.rect.height)
    .slice(0, 20);
}

function findElement(selector) {
  if (!selector) {
    throw new Error("Missing selector.");
  }

  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }

  return element;
}

function dispatchInputEvents(element) {
  element.dispatchEvent(
    new InputEvent("input", {
      bubbles: true,
      cancelable: true,
      data: element.value ?? element.textContent ?? "",
      inputType: "insertText",
    }),
  );
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function setNativeValue(element, value) {
  const prototype = Object.getPrototypeOf(element);
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");

  if (descriptor?.set) {
    descriptor.set.call(element, value);
    return;
  }

  element.value = value;
}

function typeIntoElement(element, text, shouldClear) {
  element.focus();

  if ("value" in element) {
    const currentValue = shouldClear ? "" : element.value ?? "";
    setNativeValue(element, `${currentValue}${text}`);
    dispatchInputEvents(element);
    return;
  }

  if (element.isContentEditable) {
    if (shouldClear) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }

    document.execCommand("insertText", false, text);
    dispatchInputEvents(element);
    return;
  }

  element.textContent = text;
  dispatchInputEvents(element);
}

function pressKey(key) {
  const target = document.activeElement || document.body;
  const eventOptions = {
    bubbles: true,
    cancelable: true,
    key,
  };

  target.dispatchEvent(new KeyboardEvent("keydown", eventOptions));
  target.dispatchEvent(new KeyboardEvent("keyup", eventOptions));
}

const runtimeApi = globalThis.browser?.runtime ?? globalThis.chrome.runtime;

runtimeApi.onMessage.addListener((message, _sender, sendResponse) => {
  try {
    if (message.action === "extract_state") {
      sendResponse({ ok: true, state: serializePageState() });
      return true;
    }

    if (message.action === "extract_images") {
      sendResponse({ ok: true, images: serializeImages() });
      return true;
    }

    if (message.action === "click") {
      findElement(message.selector).click();
      sendResponse({ ok: true });
      return true;
    }

    if (message.action === "type") {
      const element = findElement(message.selector);
      typeIntoElement(element, message.text ?? "", message.clear ?? true);
      sendResponse({ ok: true });
      return true;
    }

    if (message.action === "press") {
      pressKey(message.key);
      sendResponse({ ok: true });
      return true;
    }

    sendResponse({ ok: false, error: `Unsupported content action: ${message.action}` });
  } catch (error) {
    sendResponse({ ok: false, error: error instanceof Error ? error.message : "Unknown content script error." });
  }

  return true;
});
