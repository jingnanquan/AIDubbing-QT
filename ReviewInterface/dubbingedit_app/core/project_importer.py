from __future__ import annotations

import fnmatch
import json
import os
import shutil
from dataclasses import dataclass
from typing import Optional, Dict


REQUIRED_PATTERNS = {
    "original_video": "*原视频*",
    "dubbed_video": "*视频-配音*",
    "dub_vocal_audio": "*配音音频-纯人声*",
    "subtitle": "*合并后的配音字幕*",
}

OPTIONAL_PATTERNS = {
    "background": "*background*",
    "vocal": "*vocal*",
    "voice_ids": "*voice_ids.json",
}


def _find_one(files: list[str], pattern: str) -> Optional[str]:
    lower_names = [(f, f) for f in files]
    matches = [name for name, _ in lower_names if fnmatch.fnmatch(name, pattern)]
    if not matches:
        return None
    matches.sort(key=len)
    return matches[0]


@dataclass
class ProjectImportResult:
    ok: bool
    message: str
    project_dir: Optional[str] = None
    workspace_dir: Optional[str] = None
    paths: Optional["WorkspacePaths"] = None


def import_project_folder(project_dir: str) -> ProjectImportResult:
    from ReviewInterface.dubbingedit_app.core.workspace_paths import WorkspacePaths

    project_dir = os.path.abspath(project_dir)
    if not os.path.isdir(project_dir):
        return ProjectImportResult(False, "所选路径不是文件夹", None, None, None)

    try:
        names = [f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f))]
    except OSError as e:
        return ProjectImportResult(False, str(e), None, None, None)

    missing = []
    resolved: dict[str, str] = {}
    for key, pat in REQUIRED_PATTERNS.items():
        found = _find_one(names, pat)
        if not found:
            missing.append(pat)
        else:
            resolved[key] = os.path.join(project_dir, found)

    if missing:
        return ProjectImportResult(False, "项目导入失败", None, None, None)

    workspace_dir = os.path.join(project_dir, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)

    # 检查workspace是否已经存在且包含所有必需文件
    workspace_ready = True
    for key in REQUIRED_PATTERNS.keys():
        ws_file = _find_one([os.path.basename(resolved[key])], os.path.basename(resolved[key]))
        if ws_file:
            ws_path = os.path.join(workspace_dir, os.path.basename(resolved[key]))
            if not os.path.exists(ws_path):
                workspace_ready = False
                break
        else:
            workspace_ready = False
            break

    files_to_copy = list(resolved.values())
    for key, pat in OPTIONAL_PATTERNS.items():
        found = _find_one(names, pat)
        if found:
            resolved[key] = os.path.join(project_dir, found)
            files_to_copy.append(resolved[key])

    # 如果workspace已准备好（存在所有必需文件），则跳过复制
    if not workspace_ready:
        try:
            for src in files_to_copy:
                dst = os.path.join(workspace_dir, os.path.basename(src))
                # 如果目标文件已存在，跳过复制
                if os.path.exists(dst):
                    print(f"文件已存在，跳过复制: {os.path.basename(dst)}")
                    continue
                shutil.copy2(src, dst)
                print(f"已复制文件: {os.path.basename(src)}")
        except OSError as e:
            return ProjectImportResult(False, f"复制到 workspace 失败: {e}", None, None, None)
    else:
        print(f"workspace已存在且包含所有必需文件，跳过复制过程")

    project_name = os.path.basename(resolved["original_video"])

    # 解析voice_ids.json文件
    voice_ids_mapping: Dict[str, str] = {}
    if "voice_ids" in resolved:
        try:
            with open(resolved["voice_ids"], "r", encoding="utf-8") as f:
                voice_ids_mapping = json.load(f)
                print(f"成功加载voice_ids，共{len(voice_ids_mapping)}个角色")
        except Exception as e:
            print(f"解析voice_ids.json失败: {e}")

    ws_paths = WorkspacePaths.from_workspace_dir(workspace_dir, project_name, voice_ids_mapping=voice_ids_mapping)
    return ProjectImportResult(True, "导入成功", project_dir, workspace_dir, ws_paths)
