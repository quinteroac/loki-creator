import { useMemo, useRef, useState } from "react";
import {
  Archive,
  Copy,
  Download,
  FolderOpen,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { filterProjectSummaries } from "../lib/projects";
import type { ProjectStatus, ProjectSummary } from "../types";

type ProjectManagerProps = {
  currentProjectId: string | null;
  isPending: boolean;
  onArchiveProject: (projectId: string) => void;
  onClose: () => void;
  onCreateNewProject: () => void;
  onDeleteProjectForever: (projectId: string) => void;
  onDuplicateProject: (projectId: string) => void;
  onExportProject: (projectId: string) => void;
  onImportProject: (file: File) => void;
  onOpenProject: (projectId: string) => void;
  onRenameProject: (projectId: string, name: string) => void;
  onRestoreProject: (projectId: string) => void;
  onTrashProject: (projectId: string) => void;
  projects: ProjectSummary[];
};

const PROJECT_TABS: Array<{ label: string; status: ProjectStatus }> = [
  { label: "Active", status: "active" },
  { label: "Archived", status: "archived" },
  { label: "Trash", status: "trashed" },
];

function formatProjectDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function projectCountLabel(project: ProjectSummary) {
  const cardLabel = project.cardCount === 1 ? "1 card" : `${project.cardCount} cards`;
  const artifactLabel = project.artifactCount === 1 ? "1 artifact" : `${project.artifactCount} artifacts`;

  return `${cardLabel} · ${artifactLabel}`;
}

export function ProjectManager({
  currentProjectId,
  isPending,
  onArchiveProject,
  onClose,
  onCreateNewProject,
  onDeleteProjectForever,
  onDuplicateProject,
  onExportProject,
  onImportProject,
  onOpenProject,
  onRenameProject,
  onRestoreProject,
  onTrashProject,
  projects,
}: ProjectManagerProps) {
  const [activeStatus, setActiveStatus] = useState<ProjectStatus>("active");
  const [search, setSearch] = useState("");
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const filteredProjects = useMemo(
    () => filterProjectSummaries(projects, activeStatus, search),
    [activeStatus, projects, search],
  );
  const counts = useMemo(() => {
    return PROJECT_TABS.reduce<Record<ProjectStatus, number>>((result, tab) => {
      result[tab.status] = projects.filter((project) => project.status === tab.status).length;
      return result;
    }, { active: 0, archived: 0, trashed: 0 });
  }, [projects]);

  function startRenaming(project: ProjectSummary) {
    setRenamingProjectId(project.id);
    setRenameDraft(project.name);
  }

  function submitRename(projectId: string) {
    onRenameProject(projectId, renameDraft);
    setRenamingProjectId(null);
    setRenameDraft("");
  }

  function handleImportFile() {
    const file = importInputRef.current?.files?.[0];
    if (!file) return;

    onImportProject(file);
    if (importInputRef.current) {
      importInputRef.current.value = "";
    }
  }

  function deleteForever(projectId: string) {
    if (!window.confirm("Permanently delete this project?")) return;
    onDeleteProjectForever(projectId);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="project-manager" aria-label="Project manager">
        <div className="project-manager-header">
          <div>
            <h2>Projects</h2>
            <p>{projects.length === 1 ? "1 local project" : `${projects.length} local projects`}</p>
          </div>
          <button className="project-icon-button" type="button" onClick={onClose} aria-label="Close projects">
            <X aria-hidden="true" />
          </button>
        </div>

        <div className="project-manager-toolbar">
          <button className="button-primary compact" type="button" onClick={onCreateNewProject} disabled={isPending}>
            <Plus aria-hidden="true" />
            New
          </button>
          <button
            className="button-secondary compact"
            type="button"
            onClick={() => importInputRef.current?.click()}
            disabled={isPending}
          >
            <Upload aria-hidden="true" />
            Import
          </button>
          <input
            ref={importInputRef}
            className="project-import-input"
            type="file"
            accept=".zip,.loki-project.zip,application/zip"
            onChange={handleImportFile}
          />
          <label className="project-search">
            <Search aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search"
            />
          </label>
        </div>

        <div className="project-tabs" role="tablist" aria-label="Project status">
          {PROJECT_TABS.map((tab) => (
            <button
              className={activeStatus === tab.status ? "project-tab active" : "project-tab"}
              type="button"
              role="tab"
              aria-selected={activeStatus === tab.status}
              key={tab.status}
              onClick={() => setActiveStatus(tab.status)}
            >
              {tab.label}
              <span>{counts[tab.status]}</span>
            </button>
          ))}
        </div>

        <div className="project-list" aria-label={`${activeStatus} projects`}>
          {filteredProjects.map((project) => (
            <article
              className={project.id === currentProjectId ? "project-row current" : "project-row"}
              key={project.id}
            >
              <div className="project-row-main">
                {renamingProjectId === project.id ? (
                  <form
                    className="project-rename-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      submitRename(project.id);
                    }}
                  >
                    <input
                      value={renameDraft}
                      onChange={(event) => setRenameDraft(event.target.value)}
                      autoFocus
                    />
                    <button className="button-primary compact" type="submit" disabled={isPending}>
                      Save
                    </button>
                    <button
                      className="button-tertiary compact"
                      type="button"
                      onClick={() => setRenamingProjectId(null)}
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <strong>{project.name}</strong>
                    <span>
                      {projectCountLabel(project)} · Updated {formatProjectDate(project.updatedAt)}
                    </span>
                  </>
                )}
              </div>

              {renamingProjectId !== project.id && (
                <div className="project-row-actions">
                  {project.status !== "trashed" && (
                    <button type="button" onClick={() => onOpenProject(project.id)} disabled={isPending}>
                      <FolderOpen aria-hidden="true" />
                      Open
                    </button>
                  )}
                  {project.status !== "trashed" && (
                    <button type="button" onClick={() => startRenaming(project)} disabled={isPending}>
                      <Pencil aria-hidden="true" />
                      Rename
                    </button>
                  )}
                  {project.status !== "trashed" && (
                    <button type="button" onClick={() => onDuplicateProject(project.id)} disabled={isPending}>
                      <Copy aria-hidden="true" />
                      Duplicate
                    </button>
                  )}
                  {project.status !== "trashed" && (
                    <button type="button" onClick={() => onExportProject(project.id)} disabled={isPending}>
                      <Download aria-hidden="true" />
                      Export
                    </button>
                  )}
                  {project.status === "active" && (
                    <button type="button" onClick={() => onArchiveProject(project.id)} disabled={isPending}>
                      <Archive aria-hidden="true" />
                      Archive
                    </button>
                  )}
                  {project.status === "archived" && (
                    <button type="button" onClick={() => onRestoreProject(project.id)} disabled={isPending}>
                      <RotateCcw aria-hidden="true" />
                      Restore
                    </button>
                  )}
                  {project.status !== "trashed" && (
                    <button className="danger" type="button" onClick={() => onTrashProject(project.id)} disabled={isPending}>
                      <Trash2 aria-hidden="true" />
                      Trash
                    </button>
                  )}
                  {project.status === "trashed" && (
                    <>
                      <button type="button" onClick={() => onRestoreProject(project.id)} disabled={isPending}>
                        <RotateCcw aria-hidden="true" />
                        Restore
                      </button>
                      <button className="danger" type="button" onClick={() => deleteForever(project.id)} disabled={isPending}>
                        <Trash2 aria-hidden="true" />
                        Delete
                      </button>
                    </>
                  )}
                </div>
              )}
            </article>
          ))}
          {filteredProjects.length === 0 && (
            <p className="project-empty">
              No {activeStatus} projects
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
