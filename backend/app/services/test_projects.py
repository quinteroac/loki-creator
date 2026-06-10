from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models import ProjectCreateRequest, ProjectSaveRequest
from app.services.projects import (
    ProjectArtifactMissingError,
    ProjectImportError,
    ProjectInvalidOperationError,
    ProjectService,
)


def project_payload(name: str, artifact_url: str | None = None) -> dict:
    html = "<main>No artifact</main>"
    metadata = {
        "kind": "generic",
        "title": "Card",
        "description": "Test card",
    }
    if artifact_url:
        html = f'<img src="{artifact_url}" alt="Card" />'
        metadata.update(
            {
                "kind": "image",
                "artifactUrl": artifact_url,
                "thumbnailUrl": artifact_url,
            }
        )

    return {
        "name": name,
        "cardDocuments": [
            {
                "id": "card_1",
                "name": "Card",
                "prompt": "Test prompt",
                "html": html,
                "sourceSkillId": "test",
                "sourceActionId": "run",
                "metadata": metadata,
            }
        ],
        "canvasNodes": [
            {
                "id": "node_1",
                "cardDocumentId": "card_1",
                "frame": {"x": 10, "y": 20, "width": 240},
            }
        ],
    }


def create_unsafe_zip() -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format": "loki-project", "artifacts": []}))
        archive.writestr("project/project.json", json.dumps(project_payload("Unsafe")))
        archive.writestr("../escape.txt", "bad")
    return buffer.getvalue()


class ProjectServiceTest(unittest.TestCase):
    def service(self, root: Path) -> ProjectService:
        return ProjectService(root / "projects", root)

    def test_reads_v1_projects_as_active_and_saves_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_file = root / "projects" / "legacy" / "project.json"
            project_file.parent.mkdir(parents=True)
            project_file.write_text(
                json.dumps(
                    {
                        "id": "legacy",
                        "name": "Legacy",
                        "createdAt": "2026-01-01T00:00:00+00:00",
                        "updatedAt": "2026-01-01T00:00:00+00:00",
                        "cardDocuments": [],
                        "canvasNodes": [],
                    }
                ),
                encoding="utf-8",
            )
            service = self.service(root)

            project = service.get_project("legacy")
            self.assertEqual(project.schema_version, 2)
            self.assertEqual(project.status, "active")

            saved = service.save_project(
                "legacy",
                ProjectSaveRequest.model_validate({"name": "Legacy renamed", "cardDocuments": [], "canvasNodes": []}),
            )

            self.assertEqual(saved.id, "legacy")
            saved_payload = json.loads(project_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["schemaVersion"], 2)
            self.assertEqual(saved_payload["status"], "active")

    def test_create_save_and_rename_keeps_stable_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(Path(tmpdir))
            first = service.create_project(ProjectCreateRequest.model_validate(project_payload("My Project")))
            second = service.create_project(ProjectCreateRequest.model_validate(project_payload("My Project")))

            self.assertEqual(first.id, "my-project")
            self.assertEqual(second.id, "my-project-2")

            saved = service.save_project(
                first.id,
                ProjectSaveRequest.model_validate(project_payload("Renamed Project")),
            )

            self.assertEqual(saved.id, first.id)
            self.assertEqual(saved.name, "Renamed Project")
            self.assertTrue((Path(tmpdir) / "projects" / "my-project" / "project.json").is_file())

    def test_lists_by_status_and_lifecycle_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(Path(tmpdir))
            active = service.create_project(ProjectCreateRequest.model_validate(project_payload("Active")))
            archived = service.create_project(ProjectCreateRequest.model_validate(project_payload("Archived")))
            trashed = service.create_project(ProjectCreateRequest.model_validate(project_payload("Trashed")))

            service.archive_project(archived.id)
            service.trash_project(trashed.id)

            self.assertEqual([project.id for project in service.list_projects()], [active.id])
            self.assertEqual([project.id for project in service.list_projects(status="archived")], [archived.id])
            self.assertEqual([project.id for project in service.list_projects(status="trashed")], [trashed.id])
            self.assertEqual(len(service.list_projects(status="all")), 3)

            restored = service.restore_project(archived.id)
            self.assertEqual(restored.status, "active")
            self.assertIsNone(restored.archived_at)

            with self.assertRaises(ProjectInvalidOperationError):
                service.delete_project(active.id)

            service.delete_project(trashed.id)
            self.assertFalse((Path(tmpdir) / "projects" / trashed.id).exists())

    def test_duplicate_project_creates_active_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(Path(tmpdir))
            source = service.create_project(ProjectCreateRequest.model_validate(project_payload("Source")))
            service.archive_project(source.id)

            duplicate = service.duplicate_project(source.id)

            self.assertEqual(duplicate.id, "source-copy")
            self.assertEqual(duplicate.status, "active")
            self.assertEqual(len(duplicate.card_documents), 1)

    def test_export_includes_project_manifest_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = root / "imports" / "image.png"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"image")
            service = self.service(root)
            project = service.create_project(
                ProjectCreateRequest.model_validate(project_payload("Exportable", "/api/artifacts/imports/image.png"))
            )

            exported = service.export_project(project.id)

            self.assertTrue(exported.filename.endswith(".loki-project.zip"))
            with ZipFile(io.BytesIO(exported.data)) as archive:
                self.assertIn("manifest.json", archive.namelist())
                self.assertIn("project/project.json", archive.namelist())
                self.assertIn("artifacts/imports/image.png", archive.namelist())
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["format"], "loki-project")
                self.assertEqual(manifest["artifacts"][0]["sourceUrl"], "/api/artifacts/imports/image.png")

    def test_export_fails_when_referenced_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(Path(tmpdir))
            project = service.create_project(
                ProjectCreateRequest.model_validate(project_payload("Broken", "/api/artifacts/imports/missing.png"))
            )

            with self.assertRaises(ProjectArtifactMissingError):
                service.export_project(project.id)

    def test_import_rewrites_artifact_urls_and_avoids_id_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = root / "imports" / "image.png"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"image")
            service = self.service(root)
            source = service.create_project(
                ProjectCreateRequest.model_validate(project_payload("Portable", "/api/artifacts/imports/image.png"))
            )
            exported = service.export_project(source.id)

            imported = service.import_project(exported.data)

            self.assertEqual(imported.id, "portable-2")
            imported_url = "/api/artifacts/project-imports/portable-2/imports/image.png"
            self.assertIn(imported_url, imported.card_documents[0].html)
            self.assertEqual(imported.card_documents[0].metadata.artifact_url, imported_url)
            self.assertTrue((root / "project-imports" / "portable-2" / "imports" / "image.png").is_file())

    def test_import_rejects_unsafe_zip_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(Path(tmpdir))

            with self.assertRaises(ProjectImportError):
                service.import_project(create_unsafe_zip())


if __name__ == "__main__":
    unittest.main()
