"""
Skill management commands for CCMAS.

Provides commands to install, list, and uninstall skills.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, List

import yaml

from ccmas.skill.manager import SkillManager, list_skills, get_skill_manager


SKILL_FILE_NAME = "SKILL.md"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"
GITHUB_API_URL = "https://api.github.com"


COMMON_SKILL_PATHS = [
    "skills/{name}/{name}.md",
    "skills/{name}/SKILL.md",
    "skill/{name}/{name}.md",
    "skill/{name}/SKILL.md",
    "{name}/{name}.md",
    "{name}/SKILL.md",
    "SKILL.md",
]


class SkillInstaller:
    """Handles skill installation from various sources."""

    def __init__(self, skills_dir: Optional[str] = None):
        """Initialize the installer."""
        if skills_dir is None:
            skills_dir = os.path.expanduser("~/.ccmas/skills/")
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def install(self, source: str, name: Optional[str] = None) -> dict:
        """
        Install a skill from a source.

        Args:
            source: Can be:
                - GitHub repo: "user/repo" or "user/repo/skill-name"
                - GitHub file URL: direct link to SKILL.md
                - GitHub zipball URL
                - Local path (directory with SKILL.md)
            name: Optional name for the skill (defaults to repo/skill name)

        Returns:
            dict with 'success', 'name', 'message' keys
        """
        source = source.strip()

        if os.path.isdir(source):
            return self._install_from_local(source, name)

        if source.startswith("http://") or source.startswith("https://"):
            if "github.com" in source:
                return self._install_from_github(source, name)
            else:
                return self._install_from_url(source, name)

        if "/" in source:
            return self._install_from_github_repo(source, name)

        return {
            "success": False,
            "name": name or source,
            "message": f"Invalid source: {source}",
        }

    def _install_from_local(self, path: str, name: Optional[str] = None) -> dict:
        """Install from a local directory."""
        source_path = Path(path)

        skill_file = source_path / SKILL_FILE_NAME
        if not skill_file.exists():
            for item in source_path.rglob("*"):
                if item.is_file() and item.name.lower() == "skill.md":
                    skill_file = item
                    break

        if not skill_file.exists():
            return {
                "success": False,
                "name": name or source_path.name,
                "message": f"No SKILL.md found in {path}",
            }

        skill_name = name or source_path.name
        dest_path = self.skills_dir / skill_name

        if dest_path.exists():
            return {
                "success": False,
                "name": skill_name,
                "message": f"Skill '{skill_name}' already installed. Use 'ccmas skill update {skill_name}' to update.",
            }

        try:
            if source_path.is_dir():
                shutil.copytree(source_path, dest_path)
            else:
                dest_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(skill_file, dest_path / SKILL_FILE_NAME)

            self._validate_installed_skill(dest_path, skill_name)
            get_skill_manager().reload()
            return {
                "success": True,
                "name": skill_name,
                "message": f"Successfully installed skill '{skill_name}' from local path",
            }
        except Exception as e:
            if dest_path.exists():
                shutil.rmtree(dest_path, ignore_errors=True)
            return {
                "success": False,
                "name": skill_name,
                "message": f"Failed to install: {e}",
            }

    def _install_from_github(self, url: str, name: Optional[str] = None) -> dict:
        """Install from a GitHub URL."""
        url = url.rstrip("/")

        if "/tree/" in url:
            return self._install_from_github_tree_url(url, name)
        elif url.endswith(".zip") or "zipball" in url:
            return self._install_from_github_zip(url, name)
        elif url.endswith(".md") or "SKILL.md" in url:
            return self._install_from_github_file(url, name)
        else:
            return self._install_from_github_repo(url, name)

    def _install_from_github_tree_url(self, url: str, name: Optional[str] = None) -> dict:
        """Install from a GitHub tree URL (typically a directory view)."""
        match = re.match(
            r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)",
            url
        )
        if not match:
            return {
                "success": False,
                "name": name or "unknown",
                "message": f"Could not parse GitHub URL: {url}",
            }

        user, repo, branch, path = match.groups()
        skill_name = name or path.split("/")[-1]

        file_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}/{SKILL_FILE_NAME}"
        return self._install_from_url(file_url, skill_name)

    def _install_from_github_file(self, url: str, name: Optional[str] = None) -> dict:
        """Install a single SKILL.md file from GitHub."""
        match = re.search(
            r"github\.com/([^/]+)/([^/]+)/([^/]+)/(.+\.md)",
            url
        )
        if not match:
            match = re.search(
                r"raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+\.md)",
                url
            )

        if match:
            user, repo, branch, file_path = match.groups()
            skill_name = name or file_path.replace(".md", "").split("/")[-1]
        else:
            skill_name = name or "skill"

        return self._install_from_url(url, skill_name)

    def _install_from_github_zip(self, url: str, name: Optional[str] = None) -> dict:
        """Install from a GitHub zipball URL."""
        if "tarball" in url:
            return {
                "success": False,
                "name": name or "unknown",
                "message": "Tarball format not yet supported. Please use zipball or direct file URL.",
            }

        match = re.search(r"github\.com/([^/]+)/([^/]+)/zipball(?:/([^/]+))?(?:/(.+))?", url)
        if not match:
            match = re.search(r"github\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)

        if not match:
            return {
                "success": False,
                "name": name or "unknown",
                "message": f"Could not parse GitHub URL: {url}",
            }

        user, repo, branch, sub_path = match.groups()
        branch = branch or "main"

        skill_name = name or sub_path.split("/")[-1] if sub_path else repo
        dest_path = self.skills_dir / skill_name

        if dest_path.exists():
            return {
                "success": False,
                "name": skill_name,
                "message": f"Skill '{skill_name}' already installed. Use 'ccmas skill update {skill_name}' to update.",
            }

        try:
            api_url = f"https://api.github.com/repos/{user}/{repo}/zipball/{branch}"
            request = urllib.request.Request(
                api_url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CCMAS"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                zip_data = response.read()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_file = temp_path / "skill.zip"

                with open(zip_file, "wb") as f:
                    f.write(zip_data)

                with zipfile.ZipFile(zip_file, "r") as zf:
                    zf.extractall(temp_path)

                top_level = None
                for item in temp_path.iterdir():
                    if item.is_dir():
                        top_level = item
                        break

                if top_level is None:
                    return {
                        "success": False,
                        "name": skill_name,
                        "message": "Failed to extract zip archive",
                    }

                if sub_path:
                    target = top_level / sub_path
                    if target.exists() and target.is_dir():
                        shutil.copytree(target, dest_path)
                    else:
                        for item in top_level.rglob("SKILL.md"):
                            parent = item.parent
                            skill_files = list(parent.glob("*"))
                            if (parent / "SKILL.md").exists():
                                shutil.copytree(parent, dest_path)
                                break
                else:
                    has_skill = False
                    for item in top_level.rglob("SKILL.md"):
                        parent = item.parent
                        skill_files = list(parent.glob("*"))
                        if (parent / "SKILL.md").exists():
                            shutil.copytree(parent, dest_path)
                            has_skill = True
                            break

                    if not has_skill:
                        skill_md = top_level / "SKILL.md"
                        if skill_md.exists():
                            dest_path.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(skill_md, dest_path / SKILL_FILE_NAME)
                        else:
                            return {
                                "success": False,
                                "name": skill_name,
                                "message": "No SKILL.md found in repository",
                            }

            self._validate_installed_skill(dest_path, skill_name)
            get_skill_manager().reload()
            return {
                "success": True,
                "name": skill_name,
                "message": f"Successfully installed skill '{skill_name}' from {user}/{repo}",
            }

        except Exception as e:
            if dest_path.exists():
                shutil.rmtree(dest_path, ignore_errors=True)
            return {
                "success": False,
                "name": skill_name,
                "message": f"Failed to install: {e}",
            }

    def _install_from_github_repo(self, repo_spec: str, name: Optional[str] = None) -> dict:
        """Install from a GitHub repository (user/repo or user/repo/skill-name)."""
        parts = repo_spec.strip("/").split("/")

        if len(parts) >= 3:
            user, repo = parts[0], parts[1]
            skill_subpath = "/".join(parts[2:])
            skill_name = name or skill_subpath.split("/")[-1]
        elif len(parts) == 2:
            user, repo = parts
            skill_subpath = None
            skill_name = name or repo
        else:
            return {
                "success": False,
                "name": name or repo_spec,
                "message": f"Invalid repository specification: {repo_spec}",
            }

        try:
            request = urllib.request.Request(
                f"{GITHUB_API_URL}/repos/{user}/{repo}",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CCMAS"}
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                repo_info = yaml.safe_load(response)

            default_branch = repo_info.get("default_branch", "main")

            if skill_subpath:
                skill_path = f"{skill_subpath}/{SKILL_FILE_NAME}"
                file_url = f"{GITHUB_RAW_URL}/{user}/{repo}/{default_branch}/{skill_path}"
                result = self._install_from_url(file_url, skill_name)
                if result["success"]:
                    return result
                return {
                    "success": False,
                    "name": skill_name,
                    "message": f"Skill not found at {skill_subpath}/SKILL.md",
                }

            skill_paths_to_try = [
                f"skills/{skill_name}/{SKILL_FILE_NAME}",
                f"skill/{skill_name}/{SKILL_FILE_NAME}",
                f"skills/{skill_name}/{skill_name}.md",
                f"{skill_name}/{SKILL_FILE_NAME}",
                f"{skill_name}/{skill_name}.md",
                SKILL_FILE_NAME,
            ]

            for skill_path in skill_paths_to_try:
                file_url = f"{GITHUB_RAW_URL}/{user}/{repo}/{default_branch}/{skill_path}"
                result = self._install_from_url(file_url, skill_name)
                if result["success"]:
                    return result

            tree_url = f"{GITHUB_API_URL}/repos/{user}/{repo}/git/trees/{default_branch}?recursive=1"
            tree_request = urllib.request.Request(
                tree_url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CCMAS"}
            )
            with urllib.request.urlopen(tree_request, timeout=30) as response:
                tree_data = yaml.safe_load(response)

            skill_file_paths = []
            for item in tree_data.get("tree", []):
                path = item.get("path", "")
                if path.endswith("/SKILL.md") or path.endswith(f"/{skill_name}.md"):
                    skill_file_paths.append(path)

            for skill_file_path in skill_file_paths:
                file_url = f"{GITHUB_RAW_URL}/{user}/{repo}/{default_branch}/{skill_file_path}"
                skill_dir = "/".join(skill_file_path.split("/")[:-1])
                result = self._install_from_url(file_url, skill_dir.split("/")[-1])
                if result["success"]:
                    return result

            return {
                "success": False,
                "name": skill_name,
                "message": f"Could not find SKILL.md in {user}/{repo}. Try specifying path: user/repo/skill-name",
            }

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    "success": False,
                    "name": skill_name,
                    "message": f"Repository not found: {user}/{repo}",
                }
            return {
                "success": False,
                "name": skill_name,
                "message": f"GitHub API error: {e.code}",
            }
        except Exception as e:
            return {
                "success": False,
                "name": skill_name,
                "message": f"Failed to install: {e}",
            }

    def _install_from_url(self, url: str, name: Optional[str] = None) -> dict:
        """Download and install a SKILL.md file from a URL."""
        skill_name = name or url.split("/")[-1].replace(".md", "") or "skill"
        skill_name = skill_name.split("?")[0].strip()

        dest_path = self.skills_dir / skill_name
        if dest_path.exists():
            return {
                "success": False,
                "name": skill_name,
                "message": f"Skill '{skill_name}' already installed. Use 'ccmas skill update {skill_name}' to update.",
            }

        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "CCMAS"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8")

            if not self._is_valid_skill_content(content):
                return {
                    "success": False,
                    "name": skill_name,
                    "message": f"Downloaded content is not a valid SKILL.md",
                }

            dest_path.mkdir(parents=True, exist_ok=True)
            (dest_path / SKILL_FILE_NAME).write_text(content, encoding="utf-8")

            get_skill_manager().reload()
            return {
                "success": True,
                "name": skill_name,
                "message": f"Successfully installed skill '{skill_name}' from URL",
            }

        except Exception as e:
            if dest_path.exists():
                shutil.rmtree(dest_path, ignore_errors=True)
            return {
                "success": False,
                "name": skill_name,
                "message": f"Failed to download: {e}",
            }

    def _is_valid_skill_content(self, content: str) -> bool:
        """Check if content looks like a valid skill."""
        content_lower = content.lower()
        return bool(
            content.strip()
            and ("#" in content or "description" in content_lower or "instructions" in content_lower)
        )

    def _validate_installed_skill(self, skill_path: Path, skill_name: str) -> bool:
        """Ensure installed skill has a valid SKILL.md."""
        skill_file = skill_path / SKILL_FILE_NAME
        if not skill_file.exists():
            found = False
            for item in skill_path.rglob("*.md"):
                if item.name.lower() in ["skill.md", "instructions.md"]:
                    found = True
                    break
            if not found:
                shutil.rmtree(skill_path, ignore_errors=True)
                raise ValueError(f"No SKILL.md found in {skill_name}")

        content = skill_file.read_text(encoding="utf-8")
        if not self._is_valid_skill_content(content):
            shutil.rmtree(skill_path, ignore_errors=True)
            raise ValueError(f"Invalid skill content in {skill_name}")

        return True

    def uninstall(self, name: str) -> dict:
        """Uninstall a skill."""
        skill_path = self.skills_dir / name

        if not skill_path.exists():
            return {
                "success": False,
                "name": name,
                "message": f"Skill '{name}' not found",
            }

        try:
            shutil.rmtree(skill_path)
            get_skill_manager().reload()
            return {
                "success": True,
                "name": name,
                "message": f"Successfully uninstalled skill '{name}'",
            }
        except Exception as e:
            return {
                "success": False,
                "name": name,
                "message": f"Failed to uninstall: {e}",
            }

    def update(self, name: str) -> dict:
        """Update an installed skill."""
        skill_path = self.skills_dir / name

        if not skill_path.exists():
            return {
                "success": False,
                "name": name,
                "message": f"Skill '{name}' not found. Use 'ccmas skill install' instead.",
            }

        skill_file = skill_path / SKILL_FILE_NAME
        if not skill_file.exists():
            return {
                "success": False,
                "name": name,
                "message": f"Skill '{name}' has no SKILL.md file",
            }

        content = skill_file.read_text(encoding="utf-8")
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if frontmatter_match:
            try:
                fm = yaml.safe_load(frontmatter_match.group(1))
                source = fm.get("source") or fm.get("url") or fm.get("repository")
                if source:
                    shutil.rmtree(skill_path, ignore_errors=True)
                    return self.install(source, name)
            except Exception:
                pass

        return {
            "success": False,
            "name": name,
            "message": f"Could not determine update source for '{name}'. Remove and reinstall manually.",
        }


def install_skill(source: str, name: Optional[str] = None) -> dict:
    """Install a skill from a source."""
    installer = SkillInstaller()
    return installer.install(source, name)


def uninstall_skill(name: str) -> dict:
    """Uninstall a skill by name."""
    installer = SkillInstaller()
    return installer.uninstall(name)


def update_skill(name: str) -> dict:
    """Update an installed skill."""
    installer = SkillInstaller()
    return installer.update(name)


def list_installed_skills() -> list:
    """List all installed skills."""
    return list_skills()


def get_skill_info(name: str) -> Optional[dict]:
    """Get information about a specific skill."""
    skills = list_skills()
    for skill in skills:
        if skill.name == name:
            return {
                "name": skill.name,
                "description": skill.description,
                "when_to_use": skill.when_to_use,
                "allowed_tools": skill.allowed_tools,
                "version": skill.version,
                "file_path": skill.file_path,
            }
    return None