import { ACTIONS, DEFAULT_BRIDGE_WS_URL } from "./protocol.js";

const browserApi = globalThis.browser ?? globalThis.chrome;

let socket = null;
let reconnectDelayMs = 1000;

function promisify(callbackApi, context, ...args) {
  if (globalThis.browser) {
    return callbackApi.apply(context, args);
  }

  return new Promise((resolve, reject) => {
    callbackApi.apply(context, [
      ...args,
      (result) => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }

        resolve(result);
      },
    ]);
  });
}

async function getBridgeUrl() {
  const result = await promisify(browserApi.storage.local.get, browserApi.storage.local, ["bridgeWsUrl"]);
  return result.bridgeWsUrl || DEFAULT_BRIDGE_WS_URL;
}

async function getActiveTab() {
  const tabs = await promisify(browserApi.tabs.query, browserApi.tabs, { active: true, currentWindow: true });
  return tabs[0] ?? null;
}

async function ensureContentScript(tabId) {
  if (browserApi.scripting?.executeScript) {
    await promisify(browserApi.scripting.executeScript, browserApi.scripting, {
      target: { tabId },
      files: ["src/content.js"],
    });
  }
}

async function sendToContent(tabId, message) {
  await ensureContentScript(tabId);
  return promisify(browserApi.tabs.sendMessage, browserApi.tabs, tabId, message);
}

async function runAction(params) {
  const action = params.action;

  if (!ACTIONS.includes(action)) {
    throw new Error(`Unsupported browser extension action: ${action}`);
  }

  if (action === "open_url") {
    if (!params.url) throw new Error("Missing url.");
    const tab = await promisify(browserApi.tabs.create, browserApi.tabs, { url: params.url, active: true });
    return createResult(action, tab, `Opened ${params.url}`);
  }

  const tab = await getActiveTab();
  if (!tab?.id) {
    throw new Error("No active tab.");
  }

  if (action === "get_active_tab") {
    return createResult(action, tab, "Active tab resolved.");
  }

  if (action === "screenshot") {
    const screenshotDataUrl = await promisify(browserApi.tabs.captureVisibleTab, browserApi.tabs, tab.windowId, {
      format: "png",
    });
    return createResult(action, tab, "Captured visible tab screenshot.", {
      screenshotBase64: screenshotDataUrl.split(",")[1],
    });
  }

  const response = await sendToContent(tab.id, params);
  if (!response?.ok) {
    throw new Error(response?.error ?? `Content action failed: ${action}`);
  }

  if (action === "extract_state") {
    return createResult(action, tab, JSON.stringify(response.state, null, 2));
  }

  if (action === "extract_images") {
    return createResult(action, tab, JSON.stringify(response.images, null, 2));
  }

  return createResult(action, tab, `Completed ${action}.`);
}

function createResult(action, tab, observation, extra = {}) {
  return {
    ok: true,
    action,
    url: tab?.url ?? null,
    title: tab?.title ?? null,
    observation,
    ...extra,
  };
}

function connect() {
  getBridgeUrl()
    .then((url) => {
      socket = new WebSocket(url);

      socket.addEventListener("open", () => {
        reconnectDelayMs = 1000;
        socket.send(
          JSON.stringify({
            type: "hello",
            runtime: "browser-extension",
            browser: globalThis.browser ? "firefox" : "chrome",
            capabilities: ACTIONS,
          }),
        );
      });

      socket.addEventListener("message", async (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }

        if (message.type !== "command" || !message.id) return;

        try {
          const result = await runAction(message.params ?? {});
          socket.send(JSON.stringify({ type: "result", id: message.id, result }));
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : "Unknown extension error.";
          socket.send(
            JSON.stringify({
              type: "error",
              id: message.id,
              error: errorMessage,
              result: {
                ok: false,
                action: message.params?.action ?? "unknown",
                url: null,
                title: null,
                observation: `Browser extension failed: ${errorMessage}`,
                error: errorMessage,
              },
            }),
          );
        }
      });

      socket.addEventListener("close", () => {
        setTimeout(connect, reconnectDelayMs);
        reconnectDelayMs = Math.min(reconnectDelayMs * 2, 10000);
      });

      socket.addEventListener("error", () => {
        socket.close();
      });
    })
    .catch(() => {
      setTimeout(connect, reconnectDelayMs);
      reconnectDelayMs = Math.min(reconnectDelayMs * 2, 10000);
    });
}

connect();
