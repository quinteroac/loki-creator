type TopbarProps = {
  hasUnsavedChanges: boolean;
  onNewProject: () => void;
  onOpenProjectManager: () => void;
  onSaveProject: () => void;
  projectName: string;
};

export function Topbar({
  hasUnsavedChanges,
  onNewProject,
  onOpenProjectManager,
  onSaveProject,
  projectName,
}: TopbarProps) {
  return (
    <header className="topbar">
      <a className="brand" href="/" aria-label="Loki Creator">
        <span className="brand-mark" aria-hidden="true">
          L
        </span>
        <span>Loki Creator</span>
      </a>
      <div
        className="project-switcher"
        aria-label={hasUnsavedChanges ? "Current project, unsaved changes" : "Current project"}
      >
        <span className={hasUnsavedChanges ? "project-dot dirty" : "project-dot"} aria-hidden="true" />
        <span>{projectName}</span>
      </div>
      <div className="topbar-actions">
        <button
          className="button-secondary compact new-project-button"
          type="button"
          onClick={onNewProject}
          aria-label="Nuevo Proyecto"
        >
          <span className="new-project-label-full">Nuevo Proyecto</span>
          <span className="new-project-label-short" aria-hidden="true">Nuevo</span>
        </button>
        <button
          className="button-secondary compact"
          type="button"
          onClick={onOpenProjectManager}
        >
          Projects
        </button>
        <button className="button-secondary compact" type="button" onClick={onSaveProject}>
          Save
        </button>
      </div>
    </header>
  );
}
