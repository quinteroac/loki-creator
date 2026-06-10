import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  archiveProject as archiveProjectApi,
  createProject,
  deleteProject as deleteProjectApi,
  duplicateProject as duplicateProjectApi,
  exportProject as exportProjectApi,
  importProject as importProjectApi,
  listProjects,
  loadProject,
  restoreProject as restoreProjectApi,
  saveProject,
  trashProject as trashProjectApi,
} from "../api/projects";
import { normalizeCardDocument } from "../lib/cardDocuments";
import { createWorkspaceSnapshot, dedupeCanvasNodesByDocumentId } from "../lib/projects";
import type { CanvasNode, CardDocument, ProjectDocument, ProjectSummary } from "../types";

type PendingProjectAction = {
  run: () => Promise<void> | void;
};

type UseProjectsOptions = {
  cardDocuments: CardDocument[];
  canvasNodes: CanvasNode[];
  onBeforeWorkspaceReplace: () => Promise<void> | void;
  onCanvasNodesNormalized: (canvasNodes: CanvasNode[]) => void;
  onReplaceWorkspace: (cardDocuments: CardDocument[], canvasNodes: CanvasNode[], project: ProjectDocument | null) => void;
  onStatus: (message: string) => void;
};

const UNTITLED_PROJECT_NAME = "Untitled project";

export function useProjects({
  cardDocuments,
  canvasNodes,
  onBeforeWorkspaceReplace,
  onCanvasNodesNormalized,
  onReplaceWorkspace,
  onStatus,
}: UseProjectsOptions) {
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentProjectName, setCurrentProjectName] = useState(UNTITLED_PROJECT_NAME);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [savedWorkspaceSnapshot, setSavedWorkspaceSnapshot] = useState(() =>
    createWorkspaceSnapshot(cardDocuments, canvasNodes),
  );
  const [isProjectManagerOpen, setIsProjectManagerOpen] = useState(false);
  const [isSaveProjectOpen, setIsSaveProjectOpen] = useState(false);
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [isUnsavedProjectDialogOpen, setIsUnsavedProjectDialogOpen] = useState(false);
  const [isProjectActionPending, setIsProjectActionPending] = useState(false);
  const pendingActionRef = useRef<PendingProjectAction | null>(null);

  const currentWorkspaceSnapshot = useMemo(
    () => createWorkspaceSnapshot(cardDocuments, canvasNodes),
    [cardDocuments, canvasNodes],
  );
  const hasUnsavedProjectChanges = currentWorkspaceSnapshot !== savedWorkspaceSnapshot;

  const refreshProjects = useCallback(async () => {
    setProjects(await listProjects("all"));
  }, []);

  useEffect(() => {
    refreshProjects().catch(() => {
      setProjects([]);
      onStatus("Could not load projects.");
    });
  }, [onStatus, refreshProjects]);

  useEffect(() => {
    if (!hasUnsavedProjectChanges) return;

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedProjectChanges]);

  function runWhenWorkspaceClean(action: PendingProjectAction) {
    if (hasUnsavedProjectChanges) {
      pendingActionRef.current = action;
      setIsUnsavedProjectDialogOpen(true);
      setIsProjectManagerOpen(false);
      return;
    }

    void action.run();
  }

  async function applyProject(project: ProjectDocument) {
    await onBeforeWorkspaceReplace();
    const projectDocuments = project.cardDocuments.map(normalizeCardDocument);
    const projectCanvasNodes = dedupeCanvasNodesByDocumentId(project.canvasNodes);

    onReplaceWorkspace(projectDocuments, projectCanvasNodes, project);
    setCurrentProjectId(project.id);
    setCurrentProjectName(project.name);
    setSavedWorkspaceSnapshot(createWorkspaceSnapshot(projectDocuments, projectCanvasNodes));
  }

  function applyEmptyProject(statusMessage: string) {
    const emptyCardDocuments: CardDocument[] = [];
    const emptyCanvasNodes: CanvasNode[] = [];

    onReplaceWorkspace(emptyCardDocuments, emptyCanvasNodes, null);
    setCurrentProjectId(null);
    setCurrentProjectName(UNTITLED_PROJECT_NAME);
    setSavedWorkspaceSnapshot(createWorkspaceSnapshot(emptyCardDocuments, emptyCanvasNodes));
    onStatus(statusMessage);
  }

  async function openProjectNow(projectId: string) {
    try {
      setIsProjectActionPending(true);
      const project = await loadProject(projectId);
      await applyProject(project);
      setIsProjectManagerOpen(false);
      onStatus("Project opened.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not open project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  function openProject(projectId: string) {
    if (projectId === currentProjectId && !hasUnsavedProjectChanges) {
      setIsProjectManagerOpen(false);
      return;
    }

    runWhenWorkspaceClean({ run: () => openProjectNow(projectId) });
  }

  function createNewProjectNow() {
    applyEmptyProject("New project created.");
    setIsProjectManagerOpen(false);
  }

  function createNewProject() {
    runWhenWorkspaceClean({ run: createNewProjectNow });
  }

  function openSaveProjectDialog() {
    setProjectNameDraft(currentProjectName === UNTITLED_PROJECT_NAME ? "" : currentProjectName);
    setIsSaveProjectOpen(true);
    setIsUnsavedProjectDialogOpen(false);
    setIsProjectManagerOpen(false);
  }

  function closeSaveProjectDialog() {
    setIsSaveProjectOpen(false);
    pendingActionRef.current = null;
  }

  async function persistCurrentProject(name: string) {
    const trimmedName = name.trim();
    if (!trimmedName) {
      onStatus("Name the project before saving.");
      return false;
    }

    try {
      setIsProjectActionPending(true);
      const cleanCanvasNodes = dedupeCanvasNodesByDocumentId(canvasNodes);
      const payload = {
        name: trimmedName,
        cardDocuments,
        canvasNodes: cleanCanvasNodes,
      };
      const project = currentProjectId
        ? await saveProject(currentProjectId, payload)
        : await createProject(payload);

      if (cleanCanvasNodes !== canvasNodes) {
        onCanvasNodesNormalized(cleanCanvasNodes);
      }
      setCurrentProjectId(project.id);
      setCurrentProjectName(project.name);
      setSavedWorkspaceSnapshot(createWorkspaceSnapshot(cardDocuments, cleanCanvasNodes));
      await refreshProjects();
      onStatus("Project saved.");
      return true;
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not save project.");
      return false;
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function submitSaveProject() {
    const saved = await persistCurrentProject(projectNameDraft);
    if (!saved) return;

    setIsSaveProjectOpen(false);
    const pendingAction = pendingActionRef.current;
    pendingActionRef.current = null;
    if (pendingAction) {
      await pendingAction.run();
    }
  }

  function cancelPendingProjectAction() {
    pendingActionRef.current = null;
    setIsUnsavedProjectDialogOpen(false);
  }

  async function discardChangesAndRunPendingProjectAction() {
    const pendingAction = pendingActionRef.current;
    pendingActionRef.current = null;
    setIsUnsavedProjectDialogOpen(false);
    if (pendingAction) {
      await pendingAction.run();
    }
  }

  async function saveChangesAndRunPendingProjectAction() {
    if (currentProjectName === UNTITLED_PROJECT_NAME && !currentProjectId) {
      openSaveProjectDialog();
      return;
    }

    const saved = await persistCurrentProject(currentProjectName);
    if (!saved) return;

    const pendingAction = pendingActionRef.current;
    pendingActionRef.current = null;
    setIsUnsavedProjectDialogOpen(false);
    if (pendingAction) {
      await pendingAction.run();
    }
  }

  async function archiveProjectNow(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await archiveProjectApi(projectId);
      await refreshProjects();
      if (projectId === currentProjectId) {
        applyEmptyProject("Project archived.");
      } else {
        onStatus("Project archived.");
      }
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not archive project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  function archiveProject(projectId: string) {
    runWhenWorkspaceClean({ run: () => archiveProjectNow(projectId) });
  }

  async function trashProjectNow(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await trashProjectApi(projectId);
      await refreshProjects();
      if (projectId === currentProjectId) {
        applyEmptyProject("Project moved to trash.");
      } else {
        onStatus("Project moved to trash.");
      }
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not move project to trash.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  function trashProject(projectId: string) {
    runWhenWorkspaceClean({ run: () => trashProjectNow(projectId) });
  }

  async function restoreProject(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await restoreProjectApi(projectId);
      await refreshProjects();
      onStatus("Project restored.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not restore project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function deleteProjectForever(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await deleteProjectApi(projectId);
      await refreshProjects();
      onStatus("Project permanently deleted.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not permanently delete project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function duplicateProject(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await duplicateProjectApi(projectId);
      await refreshProjects();
      onStatus("Project duplicated.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not duplicate project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function exportProject(projectId: string) {
    try {
      setIsProjectActionPending(true);
      await exportProjectApi(projectId);
      onStatus("Project exported.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not export project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function importProjectNow(file: File) {
    try {
      setIsProjectActionPending(true);
      const project = await importProjectApi(file);
      await refreshProjects();
      await applyProject(project);
      setIsProjectManagerOpen(false);
      onStatus("Project imported.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not import project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  function importProjectFile(file: File) {
    runWhenWorkspaceClean({ run: () => importProjectNow(file) });
  }

  async function renameProject(projectId: string, name: string) {
    const trimmedName = name.trim();
    if (!trimmedName) {
      onStatus("Name the project before renaming.");
      return;
    }

    if (projectId === currentProjectId) {
      await persistCurrentProject(trimmedName);
      return;
    }

    try {
      setIsProjectActionPending(true);
      const project = await loadProject(projectId);
      await saveProject(project.id, {
        name: trimmedName,
        cardDocuments: project.cardDocuments,
        canvasNodes: project.canvasNodes,
      });
      await refreshProjects();
      onStatus("Project renamed.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not rename project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function openProjectManager() {
    try {
      setProjects(await listProjects("all"));
    } catch {
      setProjects([]);
      onStatus("Could not load projects.");
    }
    setIsProjectManagerOpen(true);
  }

  return {
    archiveProject,
    cancelPendingProjectAction,
    closeProjectManager: () => setIsProjectManagerOpen(false),
    closeSaveProjectDialog,
    createNewProject,
    currentProjectId,
    currentProjectName,
    deleteProjectForever,
    discardChangesAndRunPendingProjectAction,
    duplicateProject,
    exportProject,
    hasUnsavedProjectChanges,
    importProjectFile,
    isProjectActionPending,
    isProjectManagerOpen,
    isSaveProjectOpen,
    isUnsavedProjectDialogOpen,
    openProject,
    openProjectManager,
    openSaveProjectDialog,
    projectNameDraft,
    projects,
    renameProject,
    restoreProject,
    saveChangesAndRunPendingProjectAction,
    setProjectNameDraft,
    submitSaveProject,
    trashProject,
  };
}
