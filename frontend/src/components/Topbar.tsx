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
      <button className="button-secondary compact" type="button">
        Save
      </button>
    </header>
  );
}
