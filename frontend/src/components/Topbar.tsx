export function Topbar() {
  return (
    <header className="topbar">
      <a className="brand" href="/" aria-label="Loki Creator">
        <span className="brand-mark" aria-hidden="true">
          L
        </span>
        <span>Loki Creator</span>
      </a>
      <div className="project-switcher" aria-label="Current project">
        <span className="project-dot" aria-hidden="true" />
        <span>Untitled project</span>
      </div>
      <div className="topbar-actions">
        <a
          className="button-secondary compact"
          href="/downloads/browser-extension/loki-browser-extension-chrome.zip"
          download="loki-browser-extension-chrome.zip"
        >
          Chrome Extension
        </a>
        <a
          className="button-secondary compact"
          href="/downloads/browser-extension/loki-browser-extension-firefox.zip"
          download="loki-browser-extension-firefox.zip"
        >
          Firefox Extension
        </a>
        <button className="button-secondary compact" type="button">
          Save
        </button>
      </div>
    </header>
  );
}
