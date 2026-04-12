from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from typing import Optional, Dict


def _find_in_dir(directory: str, pattern: str) -> Optional[str]:
    if not os.path.isdir(directory):
        return None
    try:
        names = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    except OSError:
        return None
    matches = [n for n in names if fnmatch.fnmatch(n, pattern)]
    if not matches:
        return None
    matches.sort(key=len)
    return os.path.join(directory, matches[0])


@dataclass
class WorkspacePaths:
    workspace_dir: str
    project_name: str
    original_video: str
    dubbed_video: str
    dub_vocal_audio: str
    subtitle: str
    background: Optional[str]
    vocal: Optional[str]
    voice_ids_path: Optional[str]
    voice_ids_mapping: Dict[str, str]

    @classmethod
    def from_workspace_dir(cls, workspace_dir: str, project_name: str, voice_ids_mapping: Optional[Dict[str, str]] = None) -> WorkspacePaths:
        workspace_dir = os.path.abspath(workspace_dir)
        ov = _find_in_dir(workspace_dir, "*原视频*")
        dv = _find_in_dir(workspace_dir, "*视频-配音*")
        da = _find_in_dir(workspace_dir, "*配音音频-纯人声*")
        st = _find_in_dir(workspace_dir, "*合并后的配音字幕*")
        bg = _find_in_dir(workspace_dir, "*background*")
        vc = _find_in_dir(workspace_dir, "*vocal*")
        vi = _find_in_dir(workspace_dir, "*voice_ids.json")
        if not all([ov, dv, da, st]):
            raise ValueError("workspace 内缺少必需文件")
        return cls(
            workspace_dir=workspace_dir,
            project_name=project_name,
            original_video=ov,
            dubbed_video=dv,
            dub_vocal_audio=da,
            subtitle=st,
            background=bg,
            vocal=vc,
            voice_ids_path=vi,
            voice_ids_mapping=voice_ids_mapping if voice_ids_mapping is not None else {},
        )

    def refresh_optional(self) -> None:
        self.background = _find_in_dir(self.workspace_dir, "*background*")
        self.vocal = _find_in_dir(self.workspace_dir, "*vocal*")
        self.voice_ids_path = _find_in_dir(self.workspace_dir, "*voice_ids.json")
