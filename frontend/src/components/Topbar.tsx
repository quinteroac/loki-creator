import type { ProjectSummary } from "../types";

type TopbarProps = {
  isProjectMenuOpen: boolean;
  onOpenProject: (projectId: string) => void;
  onSaveProject: () => void;
  onToggleProjectMenu: () => void;
  projectName: string;
  projects: ProjectSummary[];
};

export function Topbar({
  isProjectMenuOpen,
  onOpenProject,
  onSaveProject,
  onToggleProjectMenu,
  projectName,
  projects,
}: TopbarProps) {
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
        <span>{projectName}</span>
      </div>
      <div className="topbar-actions">
        <button
          className="button-secondary compact"
          type="button"
          data-popover-trigger
          aria-expanded={isProjectMenuOpen}
          onClick={onToggleProjectMenu}
        >
          Open
        </button>
        {isProjectMenuOpen && (
          <div className="popover project-popover" data-popover aria-label="Open project">
            {projects.map((project) => (
              <button type="button" key={project.id} onClick={() => onOpenProject(project.id)}>
                <strong>{project.name}</strong>
                <small>
                  {project.cardCount === 1 ? "1 card" : `${project.cardCount} cards`}
                </small>
              </button>
            ))}
            {projects.length === 0 && <p className="picker-empty">No saved projects</p>}
          </div>
        )}
        <button className="button-secondary compact" type="button" onClick={onSaveProject}>
          Save
        </button>
      </div>
    </header>
  );
}
